from flask import Flask, render_template, request, send_file
import requests
import csv
import os
import io
import zipfile
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route("/download_pdfs", methods=["POST"])
def download_pdfs():
    pdf_urls = request.json.get('pdf_urls', [])
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for i, url in enumerate(pdf_urls):
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    zip_file.writestr(f"paper_{i+1}.pdf", response.content)
            except Exception as e:
                print(f"PDF download error for {url}: {e}")

    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='papers.zip')

# 여기에 기존의 search_pubmed(), summarize_text(), index(), download() 함수 포함됨
# 사용자 코드와 병합 필요
