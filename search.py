import os
from typing import List
import torch
from transformers import AutoTokenizer, AutoModel
from pymilvus import (
    connections, FieldSchema, CollectionSchema, DataType,
        Collection, utility
        )

from pymilvus import (
    MilvusClient,
    DataType,
    Function,
    FunctionType,
    AnnSearchRequest,
    RRFRanker,
)

import json
from langchain_core.documents import Document
import insert5
import restore

uri = "http://localhost:19530"
collection_name = "text_files_kakaobank_deberta"
client = MilvusClient(uri=uri)

query = "공정거래"
query_embedding = insert5.embed_texts([query])[0]

client = MilvusClient(uri=uri)

results = client.search(
    collection_name=collection_name,
    data=[query_embedding],
    anns_field="embedding",
    limit=5,
    output_fields=["docID", "page","text"],
    group_by_field="docID",
)

for i, result in enumerate(results[0]):
    #print(f"Score: {result['distance']:.4f}, content: {result['entity']['text']}, page: {result['entity']['page']}")
    print(f"Score: {result['distance']:.4f}")
    filter_expr = "docID == {docID}"
    filter_params = {"docID" : result['entity']['docID']}
    res = client.query(
        collection_name=collection_name,
        filter=filter_expr,
        output_fields=["docID", "page","mother", "text"],
        filter_params=filter_params,
    )
    print(res)
    print('-'*40)
    pages = []
    mothers = []
    texts = []
    for p in res:
        pages.append(p["page"]) 
        mothers.append(p["mother"])
        texts.append(p["text"]) 
    translated_mothers = []
    for m in mothers:
        if m == -1:
            translated_mothers.append(-1)
        else:
            for ind, p_num in enumerate(pages):
                if m == p_num:
                    translated_mothers.append(ind)
                    break

    indexes = sorted(range(len(pages)), key=lambda k: pages[k], reverse=False)
    for i in indexes[:-1]:
        merged = restore.merge_sentences(texts[translated_mothers[i]], texts[i])
        texts[translated_mothers[i]] = merged
    print(texts[indexes[-1]])
    print('- - - - - -'*10)
        
