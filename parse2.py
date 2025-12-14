import json
from collections.abc import Iterable
from langchain_core.documents import Document
import sys
import os

def extract_article_number(article_name):
    number = ""        
    for c in article_name[1:]:
        if c >= '0' and c <= '9':
            number += c
        else:
            break
    if article_name[1+len(number)] != '조' or 1+len(number)+1 >= len(article_name) or article_name[1+len(number)+1] != '의':   # 251203_2
        return number
    number_2 = ""
    for c in article_name[1+len(number)+2:]:   # 251202_1
        if c >= '0' and c <= '9':
            number_2 += c
        else:
            break
    return number+"_"+number_2



def seek_into_paragraph(data, name, effective_date, chapter, article, page):
    content = ""
    docs = []
    if not isinstance(data, list) and data.get("호"):
        subcontent, children, page =  seek_into_subparagraph(data["호"],name, effective_date, chapter, article, page)
        content = content + "\n" + subcontent
        return content, children, page
    elif not isinstance(data, list) and data.get("항내용"):   # 251203_3
        return data["항내용"], [], page
    else:
        for entry in data:
            if entry.get("항내용") and isinstance(entry["항내용"], list): # 251202_2 and 251203_6
                content = content + "\n"
                for s in entry["항내용"][0]:
                    content = content + s
            elif entry.get("항내용"):   # 251203_6
                content = content + "\n" + entry["항내용"]
            if entry.get("호"):
                subcontent, children, page = seek_into_subparagraph(entry["호"], name, effective_date, chapter, article, page)
                parent = Document(
                        page_content=content+"\n"+subcontent,
                        metadata={
                            "name": name,
                            "effective_date": effective_date,
                            "chapter": chapter,
                            "article": article,
                            "length": len(content+"\n"+subcontent),
                            "page": page,
                            "mother": -1,
                        }                    
                )    
                docs.append(parent)
                for child in children:
                    child.metadata["mother"] = page
                    docs.append(child)
                page += 1
    return content, docs, page

def seek_into_subparagraph(data, name, effective_date, chapter, article, page):
    content = ""
    docs = []
    if not isinstance(data, list) and data.get("호내용"):  # 251203_5
        if isinstance(data["호내용"],list):
            content = ""
            for s in data["호내용"][0]:
                content = content + "\n" + s
        else:
            content = data["호내용"]
        return content, [], page
    for entry in data:
        if not isinstance(entry["호내용"], list):
            content = content + "\n" + entry["호내용"]
        else:
            subcontent = ""
            for s in entry["호내용"][0]:
                subcontent = subcontent + s 
            content = content + "\n" + subcontent
            #content = content + "\n" + entry["호내용"][0][0] ## [[ ]]
            
        if entry.get("목"):
            subcontent = seek_into_item(entry["목"])
            parent = Document(
                        page_content=content+"\n"+subcontent,
                        metadata={
                            "name": name,
                            "effective_date": effective_date,
                            "chapter": chapter,
                            "article": article,
                            "length": len(content+"\n"+subcontent),
                            "page": page,
                            "mother": -1,
                        }                    
            )    
            page += 1
            docs.append(parent)
    return content, docs, page

def seek_into_item(data):
    content = ""
    if not isinstance(data, list) and data.get("목내용"):
        if isinstance(data["목내용"],list):
            for s in data["목내용"][0]:
                content = content + "\n" + s
        else:
            content = data["목내용"]
        return content
    for entry in data:
        if isinstance(entry["목내용"], list):   # 251202_2
            for s in entry["목내용"][0]:
                content = content + "\n" + s
        else:
            content = content + "\n" + entry["목내용"]
    return  content 

                    
def read_json_directory(file_dir):
    for fname in os.listdir(file_dir):
        file_path = os.path.join(file_dir, fname)
        """Reads a JSON file and returns the data."""
        chapter = ""
        article = "0"
        page = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        basic = json.dumps(data["법령"]["기본정보"] , ensure_ascii=False)
        name = data["법령"]["기본정보"]["법령명_한글"]
        basic = basic.replace("{", "").replace("}", "").replace("\n","").replace(" ", "").replace("\t", "")
        basic_doc = Document(
                        page_content=basic,
                        metadata={
                            "name": name,
                            "effective_date": data["법령"]["기본정보"]["시행일자"],
                            "chapter": chapter,
                            "article": article,
                            "length": len(basic),
                            "page": page,
                            "mother": -1,
                        }
        )
        page += 1
        yield basic_doc
    
        if not isinstance(data["법령"]["조문"]["조문단위"], list):   # 251203_1
            entry = data["법령"]["조문"]["조문단위"]
            content = ""
            if isinstance(entry["조문내용"], list):
                for s in entry["조문내용"][0]:
                    content = content +  '\n' + s
            else:
                content = entry["조문내용"]
            doc = Document(
                page_content=content,
                metadata={
                    "name": name,
                    "effective_date": entry["조문시행일자"],
                    "chapter": chapter,
                    "article": article,
                    "length": len(content), 
                    "page": page,
                    "mother": -1,
                }
            )
            yield doc    
        else:
            for entry in data["법령"]["조문"]["조문단위"]:
                if entry["조문여부"] == "조문":
                    if isinstance(entry["조문내용"], list):  # 251201_1
                        content = "" 
                        for s in entry["조문내용"][0]:
                            content = content + s
                    else:
                        content = entry["조문내용"]
                    effective_date = entry["조문시행일자"]
                    article = extract_article_number(content)
                    if entry.get("항"):
                        subcontent, children, page = seek_into_paragraph(entry["항"], name, effective_date, chapter, article, page)
                        content = content + "\n" + subcontent
                        doc = Document(
                            page_content=content,  #251203_4
                            metadata={
                                "name": name,
                                "effective_date": effective_date,
                                "chapter": chapter,
                                "article": article,
                                "length": len(content),
                                "page": page,
                                "mother": -1,
                            }
                        )
                        yield doc
                        for child in children:
                            child.metadata["mother"] = page
                            yield child
                        page += 1
                    else:   # without paragraph 
                        doc = Document(
                            page_content=content,
                            metadata={
                                "name": name,
                                "effective_date": effective_date,
                                "chapter": chapter,
                                "article": article,
                                "length": len(content),
                                "page": page,
                                "mother": -1,
                            }
                        )
                        page += 1
                        yield doc  
     
                elif entry["조문여부"] == "전문":
                    if isinstance(entry["조문내용"], list):   # 251204_1
                        chapter = ""
                        for s in entry["조문내용"][0]:
                            chapter = chapter + s
                        chapter = chapter[:50]  # truncate 
                    else:
                        chapter = entry["조문내용"]
                else:
                    raise Exception("Unexpected 조문여부")
    
     
if __name__ == "__main__":
    #file_path = sys.argv[1]
    #file_path = 'data.org/113181.json'
    #file_path = 'data.org/85120.json'
    #file_path = "85120.json"
    #for doc in read_json_file(file_path):
    #    print(doc)
    #    print('--' * 20)
    for doc in read_json_directory("./data"):
        #print(doc)
        print('--'* 20)
