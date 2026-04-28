import aiohttp
import asyncio
import json
import zipfile
import re
from datetime import datetime
from pathlib import Path

SEM_MAX = 1
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


async def download_and_extract(session, url, processed_data):
    if url in processed_data:
        print(f"[JUMP] {url} já processado")
        return

    async with sem:
        await asyncio.sleep(1)

        try:
            print(f"[DOWNLOAD] {url}")

            temp_file = f"temp_{Path(url).name}"

            async with session.get(url, timeout=None) as resp:
                if resp.status != 200:
                    print(f"[X] {url} -> {resp.status}")
                    return

                # download streaming (IMPORTANTE)
                with open(temp_file, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)

            if temp_file.lower().endswith(".zip"):
                await extract_from_zip(temp_file, url, processed_data)

            Path(temp_file).unlink(missing_ok=True)

        except Exception as e:
            print(f"[ERRO] {url} -> {e}")


async def extract_from_zip(zip_path, url, processed_data):
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for file_info in zip_ref.filelist:

                name = file_info.filename.lower()

                if name.endswith("ragexe.exe") or name.endswith("ragexe_re.exe"):
                    
                    # mesmo nome do link
                    new_name = Path(url).with_suffix(".exe").name

                    output_path = Path("ragexe_files") / new_name
                    output_path.parent.mkdir(exist_ok=True)

                    with zip_ref.open(file_info) as source, open(output_path, "wb") as target:
                        target.write(source.read())

                    print(f"[EXTRACTED] {new_name}")

                    processed_data[url] = {
                        "status": "completed",
                        "date_processed": datetime.now().isoformat(),
                        "ragexe_extracted": new_name,
                    }
                    return

        print(f"[NO_RAGEXE] {url}")
        processed_data[url] = {
            "status": "no_ragexe_found",
            "date_processed": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"[EXTRACT_ERROR] {url} -> {e}")
        processed_data[url] = {
            "status": "extract_error",
            "error": str(e),
            "date_processed": datetime.now().isoformat(),
        }


async def main():
    with open("links_validos.md", "r") as f:
        links = [
            line.strip()
            for line in f
            if line.strip()
            and not line.startswith("Links")
            and not line.startswith("------")
        ]

    zip_links = [url for url in links if url.lower().endswith(".zip")]

    processed_data = load_processed_links()

    async with aiohttp.ClientSession() as session:
        tasks = [download_and_extract(session, url, processed_data) for url in zip_links]
        await asyncio.gather(*tasks)

    save_processed_links(processed_data)
    print(f"\nProcessados {len(zip_links)} arquivos ZIP")


if __name__ == "__main__":
    asyncio.run(main())
