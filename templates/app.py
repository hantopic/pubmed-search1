from flask import Flask, render_template, request, jsonify
import requests
import time
from bs4 import BeautifulSoup

app = Flask(__name__)

def summarize_text(text, max_words=300):
    if not text:
        return "(No abstract available)"
    words = text.split()
    return " ".join(words[:max_words]) + "..." if len(words) > max_words else text

def search_pubmed(query, start=0, batch_size=100):
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retstart": start,
        "retmax": batch_size,
        "sort": "relevance"
    }
    search_resp = requests.get(search_url, params=search_params).json()
    ids = search_resp.get("esearchresult", {}).get("idlist", [])
    total_count = int(search_resp.get("esearchresult", {}).get("count", "0"))

    results = []
    for i in range(0, len(ids), 100):
        batch_ids = ids[i:i + 100]
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
                title = article.ArticleTitle.text.strip() if article.ArticleTitle else ""
                authors = ", ".join([
                    f"{a.LastName.text} {a.Initials.text}"
                    for a in article.find_all("Author")
                    if a.LastName and a.Initials
                ])
                journal = article.Article.Journal.Title.text if article.Article.Journal and article.Article.Journal.Title else ""
                year = article.Article.Journal.JournalIssue.PubDate.Year.text if article.Article.Journal.JournalIssue and article.Article.Journal.JournalIssue.PubDate.Year else ""
                volume = article.Article.Journal.JournalIssue.Volume.text if article.Article.Journal.JournalIssue and article.Article.Journal.JournalIssue.Volume else ""
                issue = article.Article.Journal.JournalIssue.Issue.text if article.Article.Journal.JournalIssue and article.Article.Journal.JournalIssue.Issue else ""
                pages = article.Article.Pagination.MedlinePgn.text if article.Article.Pagination and article.Article.Pagination.MedlinePgn else ""
                article_id = article.MedlineCitation.PMID.text
                article_number = ""
                for aid in article.ArticleIdList.find_all("ArticleId"):
                    if aid["IdType"] == "doi":
                        article_number = aid.text
                abstract = article.Article.Abstract.AbstractText.text if article.Article.Abstract and article.Article.Abstract.AbstractText else ""
                keywords = [kw.text for kwlist in article.find_all("KeywordList") for kw in kwlist.find_all("Keyword")]
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
    return results, total_count

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form["keyword"]
    start = int(request.form.get("start", 0))
    count = int(request.form.get("count", 100))
    results, total = search_pubmed(query, start=start, batch_size=count)
    has_more = (start + len(results)) < total
    return jsonify({
        "articles": results,
        "next_start": start + len(results),
        "has_more": has_more
    })

if __name__ == "__main__":
    app.run(debug=True)
