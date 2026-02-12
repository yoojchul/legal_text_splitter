import os
from typing import List
import torch
from transformers import AutoTokenizer, AutoModel
from pymilvus import (
    connections, FieldSchema, CollectionSchema, DataType,
    Collection, utility
)
import json
from langchain_core.documents import Document
import parse2

###############################################################################
# 설정
###############################################################################
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
COLLECTION_NAME = "text_files_kakaobank_deberta"
TEXT_DIR = "./data"    # 텍스트 파일들이 있는 디렉토리
BATCH_SIZE = 32

MODEL_NAME = "kakaobank/kf-deberta-base"

###############################################################################
# 임베딩 모델 로드 (Hugging Face)
###############################################################################
device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME).to(device)
model.eval()

def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    여러 개 문장을 입력받아 임베딩 리스트 반환.
    DeBERTa-base: CLS 임베딩 사용.
    """
    with torch.no_grad():
        tokens = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(device)

        outputs = model(**tokens)
        # [CLS] 임베딩
        cls_embeddings = outputs.last_hidden_state[:, 0, :]
        return cls_embeddings.cpu().numpy().tolist()


###############################################################################
# Milvus 컬렉션 생성 또는 로드
###############################################################################
def get_or_create_collection(name: str, dim: int) -> Collection:
    if utility.has_collection(name):
        print(f"기존 컬렉션 로드: {name}")
        return Collection(name)

    id_field = FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
        auto_id=True
    )
    law_field = FieldSchema(
        name="law",
        dtype=DataType.VARCHAR,
        max_length=512
    )    
    effective_field = FieldSchema(
        name="effective_date",
        dtype=DataType.VARCHAR,
        max_length=50
    )   
    chapter_field = FieldSchema(
        name="chapter",
        dtype=DataType.VARCHAR,
        max_length=512
    )    
    article_field = FieldSchema(
        name="article",
        dtype=DataType.VARCHAR,
        max_length=100
    ) 
    docID_field = FieldSchema(
        name="docID",
        dtype=DataType.VARCHAR,
        max_length=512
    )     
    page_field = FieldSchema(
        name="page",
        dtype=DataType.INT32,
    )     
    mother_field = FieldSchema(
        name="mother",
        dtype=DataType.INT32,
    )     
    text_field = FieldSchema(
        name="text",
        dtype=DataType.VARCHAR,
        max_length=65535
    )
    emb_field = FieldSchema(
        name="embedding",
        dtype=DataType.FLOAT_VECTOR,
        dim=dim
    )

    schema = CollectionSchema(
        fields=[
            id_field, 
            law_field, effective_field, chapter_field, article_field, docID_field, 
            page_field, mother_field, text_field, emb_field],
        description="text files with kakaobank/kf-deberta-base embeddings"
    )

    print(f"컬렉션 생성: {name}")
    return Collection(name=name, schema=schema)


###############################################################################
# 텍스트 파일 읽기
###############################################################################
def read_text_files(directory: str):
    """
    모든 .txt 파일을 (id, text) 튜플로 yield
    id = 파일 이름
    text = 전체 파일 내용
    """

    for fname in os.listdir(directory):
        if fname.lower().endswith(".json"):
            path = os.path.join(directory, fname)
            return parse2.read_json_file(path)

###############################################################################
# 메인 로직
###############################################################################
def main():
    # 1. Milvus 연결
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    print("Milvus 연결 완료")

    # 2. 임베딩 차원
    dim = model.config.hidden_size
    print("임베딩 차원:", dim)

    # 3. 컬렉션 생성
    collection = get_or_create_collection(COLLECTION_NAME, dim)

    # 4. batch insert 준비
    law_batch = []
    effective_batch = []
    chapter_batch = []
    article_batch = []
    docID_batch = []
    page_batch = []
    mother_batch = []
    texts_batch = []
    count = 0

    for doc in parse2.read_json_directory(TEXT_DIR):
#        print(doc.metadata["name"])
#        print(doc.page_content)
#        print("-"*40)
        law_batch.append(doc.metadata["name"])
        effective_batch.append(doc.metadata["effective_date"])
        chapter_batch.append(doc.metadata["chapter"])
        article_batch.append(doc.metadata["article"])
        docID_batch.append(doc.metadata["name"].strip()+str(doc.metadata["article"]))
        page_batch.append(doc.metadata["page"])
        mother_batch.append(doc.metadata["mother"])
        texts_batch.append(doc.page_content)

        # batch full → insert
        if len(law_batch) >= BATCH_SIZE:
            embeddings_batch = embed_texts(texts_batch)
            entities = [law_batch, effective_batch, chapter_batch, 
                        article_batch, docID_batch, page_batch,  mother_batch, texts_batch, 
                        embeddings_batch]
            collection.insert(entities)

            count += len(law_batch)
            print(f"{count}개 insert 완료")

            law_batch = []
            effective_batch = []
            chapter_batch = []
            article_batch = []
            docID_batch = []
            page_batch = []
            mother_batch = []
            texts_batch = []

    # 5. 마지막 배치 처리
    if law_batch:
        embeddings_batch = embed_texts(texts_batch)
        entities = [law_batch, effective_batch, chapter_batch, 
                    article_batch, docID_batch, page_batch, mother_batch, texts_batch, 
                    embeddings_batch]
        collection.insert(entities)

        count += len(law_batch)
        print(f"마지막 배치 추가 → 총 {count}개 insert 완료")

    # 6. 인덱스 생성
    print("embedding 필드 인덱스 생성 중...")
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
        "params": {"nlist": 1024}
    }
    collection.create_index("embedding", index_params)
    print("인덱스 생성 완료")

    collection.load()
    print("컬렉션 로드 완료")
    print("총 저장 데이터 수:", collection.num_entities)


if __name__ == "__main__":
    main()

