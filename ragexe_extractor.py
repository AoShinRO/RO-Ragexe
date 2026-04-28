import aiohttp  
import asyncio  
import json  
import zipfile  
import re  
from datetime import datetime  
from pathlib import Path  
  
SEM_MAX = 3  # Reduzido para downloads maiores  
sem = asyncio.Semaphore(SEM_MAX)  
  
def load_processed_links():  
    try:  
        with open("processed_links.json", "r") as f:  
            return json.load(f)  
    except FileNotFoundError:  
        return {}  
  
def save_processed_links(data):  
    with open("processed_links.json", "w") as f:  
        json.dump(data, f, indent=2)  
  
def extract_date_from_url(url):  
    # Extrai data do padrão URL como em rosetupfinder.py [3](#2-2)   
    match = re.search(r'(\d{6})', url)  
    if match:  
        date_str = match.group(1)  
        return f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"  
    return "unknown-date"  
  
async def download_and_extract(session, url, processed_data):  
    if url in processed_data:  
        print(f"[JUMP] {url} já processado")  
        return  
  
    async with sem:  
        await asyncio.sleep(0.3)  # Rate limit maior para downloads  
        try:  
            print(f"[DOWNLOAD] {url}")  
            async with session.get(url, timeout=30) as resp:  
                if resp.status != 200:  
                    print(f"[X] {url} -> {resp.status}")  
                    return  
  
                # Download do arquivo  
                content = await resp.read()  
                temp_file = f"temp_{url.split('/')[-1]}"  
                  
                with open(temp_file, "wb") as f:  
                    f.write(content)  
  
                # Extração  
                if temp_file.endswith('.zip'):  
                    await extract_from_zip(temp_file, url, processed_data)  
                  
                # Limpeza  
                Path(temp_file).unlink(missing_ok=True)  
  
        except Exception as e:  
            print(f"[ERRO] {url} -> {e}")  
  
async def extract_from_zip(zip_path, url, processed_data):  
    try:  
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:  
            # Procura por ragexe.exe em subdiretórios  
            for file_info in zip_ref.filelist:  
                if file_info.filename.lower().endswith('ragexe.exe'):  
                    # Extrai e renomeia  
                    date_str = extract_date_from_url(url)  
                    new_name = f"{date_str}Ragexe.exe"  
                      
                    output_path = Path("ragexe_files") / new_name  
                    output_path.parent.mkdir(exist_ok=True)  
                      
                    with zip_ref.open(file_info) as source, open(output_path, "wb") as target:  
                        target.write(source.read())  
                      
                    print(f"[EXTRACTED] {new_name}")  
                      
                    # Marca como processado  
                    processed_data[url] = {  
                        "status": "completed",  
                        "date_processed": datetime.now().isoformat(),  
                        "ragexe_extracted": new_name  
                    }  
                    return  
  
        print(f"[NO_RAGEXE] {url}")  
        processed_data[url] = {  
            "status": "no_ragexe_found",  
            "date_processed": datetime.now().isoformat()  
        }  
  
    except Exception as e:  
        print(f"[EXTRACT_ERROR] {url} -> {e}")  
        processed_data[url] = {  
            "status": "extract_error",  
            "error": str(e),  
            "date_processed": datetime.now().isoformat()  
        }  
  
async def main():  
    # Carrega links válidos  
    with open("links_validos.md", "r") as f:  
        links = [line.strip() for line in f if line.strip() and not line.startswith("Links") and not line.startswith("------")]  
      
    # Filtra apenas .zip/.rar  
    zip_links = [url for url in links if url.endswith(('.zip', '.rar'))]  
      
    processed_data = load_processed_links()  
      
    async with aiohttp.ClientSession() as session:  
        tasks = []  
        for url in zip_links:  
            tasks.append(download_and_extract(session, url, processed_data))  
          
        await asyncio.gather(*tasks)  
      
    save_processed_links(processed_data)  
    print(f"\nProcessados {len(zip_links)} arquivos ZIP/RAR")  
  
if __name__ == "__main__":  
    asyncio.run(main())
