from flask import Flask, render_template, request, send_file
import requests
import csv
import os
import io
from bs4 import BeautifulSoup

app = Flask(__name__)

def search_pubmed(query, max_results=20):
    # ESearch: get list of PubMed IDs
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

    # EFetch: get detailed info
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml"
    }
    fetch_resp = requests.get(fetch_url, params=fetch_params)
    soup = BeautifulSoup(fetch_resp.content, "xml")

    results = []
    for article in soup.find_all("PubmedArticle"):
        try:
            title = article.ArticleTitle.text.strip()
            authors = ", ".join([f"{a.LastName.text} {a.Initials.text}" for a in article.find_all("Author") if a.LastName and a.Initials])
            year = article.Article.Journal.JournalIssue.PubDate.Year.text
            volume = article.Article.Journal.JournalIssue.Volume.text if article.Article.Journal.JournalIssue.Volume else ""
            issue = article.Article.Journal.JournalIssue.Issue.text if article.Article.Journal.JournalIssue.Issue else ""
            pages = article.Article.Pagination.MedlinePgn.text if article.Article.Pagination and article.Article.Pagination.MedlinePgn else ""
            article_id = article.MedlineCitation.PMID.text
            article_number = ""
            for aid in article.ArticleIdList.find_all("ArticleId"):
                if aid["IdType"] == "doi":
                    article_number = aid.text
            abstract = article.Article.Abstract.AbstractText.text if article.Article.Abstract and article.Article.Abstract.AbstractText else ""
            pdf_link = f"https://pubmed.ncbi.nlm.nih.gov/{article_id}/"

            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "volume": volume,
                "issue": issue,
                "pages": pages if pages else article_number,
                "pmid": article_id,
                "pdf_link": pdf_link,
                "summary": summarize_text(abstract)
            })
        except Exception as e:
            continue

    return results

def summarize_text(text, max_words=300):
    if not text:
        return "(No abstract available)"
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    query = ""
    if request.method == "POST":
        query = request.form["keyword"]
        results = search_pubmed(query)
    return render_template("index.html", results=results, query=query)

@app.route("/download", methods=["POST"])
def download():
    data = request.form.get("csv_data")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["제목", "저자", "발행 연도", "권", "호", "페이지/논문번호", "PMID", "PDF 링크", "요약"])
    for row in eval(data):
        writer.writerow([row['title'], row['authors'], row['year'], row['volume'], row['issue'], row['pages'], row['pmid'], row['pdf_link'], row['summary']])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    output.close()
    return send_file(mem, mimetype='text/csv', download_name='pubmed_results.csv', as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
