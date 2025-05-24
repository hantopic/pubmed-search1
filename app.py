from flask import Flask, render_template, request, send_file, session
import requests
import csv
import os
import io
import json
import time
import uuid
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = 'very-secret-key'

def search_pubmed(query, max_results=100):
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance"
    }
    search_resp = requests.get(search_url, params=search_params).json()
    ids = search_resp.get("esearchresult", {}).get("idlist", [])

    results = []
    BATCH_SIZE = 200
    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i:i + BATCH_SIZE]
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(batch_ids),
            "retmode": "xml"
        }
        fetch_resp = requests.get(fetch_url, params=fetch_params)
        soup = BeautifulSoup(fetch_resp.content, "xml")
        time.sleep(0.4)

        for article in soup.find_all("PubmedArticle"):
            try:
                title = article.ArticleTitle.text.strip()
                authors = ", ".join([
                    f"{a.LastName.text} {a.Initials.text}"
                    for a in article.find_all("Author")
                    if a.LastName and a.Initials
                ])
                journal = article.Article.Journal.Title.text if article.Article.Journal and article.Article.Journal.Title else ""
                year = article.Article.Journal.JournalIssue.PubDate.Year.text if article.Article.Journal.JournalIssue.PubDate.Year else ""
                volume = article.Article.Journal.JournalIssue.Volume.text if article.Article.Journal.JournalIssue.Volume else ""
                issue = article.Article.Journal.JournalIssue.Issue.text if article.Article.Journal.JournalIssue.Issue else ""
                pages = article.Article.Pagination.MedlinePgn.text if article.Article.Pagination and article.Article.Pagination.MedlinePgn else ""
                article_id = article.MedlineCitation.PMID.text
                article_number = ""
                for aid in article.ArticleIdList.find_all("ArticleId"):
                    if aid["IdType"] == "doi":
                        article_number = aid.text
                abstract = article.Article.Abstract.AbstractText.text if article.Article.Abstract and article.Article.Abstract.AbstractText else ""
                keywords = []
                for kwlist in article.find_all("KeywordList"):
                    for kw in kwlist.find_all("Keyword"):
                        keywords.append(kw.text)
                keyword_str = ", ".join(keywords)
                pdf_link = f"https://pubmed.ncbi.nlm.nih.gov/{article_id}/"

                results.append({
                    "title": title,
                    "authors": authors,
                    "journal": journal,
                    "year": year,
                    "volume": volume,
                    "issue": issue,
                    "pages": pages if pages else article_number,
                    "pmid": article_id,
                    "pdf_link": pdf_link,
                    "keywords": keyword_str,
                    "summary": summarize_text(abstract)
                })
            except Exception:
                continue
    return results

def summarize_text(text, max_words=300):
    if not text:
        return "(No abstract available)"
    words = text.split()
    return " ".join(words[:max_words]) + "..." if len(words) > max_words else text

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    session_id = ""
    if request.method == "POST":
        query = request.form["keyword"]
        count = int(request.form.get("count", 100))
        results = search_pubmed(query, count)
        session_id = str(uuid.uuid4())
        session[session_id] = results
    return render_template("index.html", results=results, query=query, session_id=session_id)

@app.route("/download/<session_id>")
def download(session_id):
    results = session.get(session_id, [])
    if not results:
        return "세션이 만료되었거나 결과가 없습니다.", 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["제목", "저자", "학술지명", "발행 연도", "권", "호", "페이지/논문번호", "PMID", "PDF 링크", "키워드", "요약"])
    for row in results:
        writer.writerow([
            row['title'], row['authors'], row['journal'], row['year'],
            row['volume'], row['issue'], row['pages'], row['pmid'],
            row['pdf_link'], row['keywords'], row['summary']
        ])
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    output.close()
    return send_file(mem, mimetype='text/csv', download_name='pubmed_results.csv', as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
