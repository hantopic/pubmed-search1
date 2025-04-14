from flask import Flask, render_template, request, send_file
from Bio import Entrez
import io
import csv
import os
import json

app = Flask(__name__)
Entrez.email = "your_email@example.com"  # Replace with your email

def fetch_pubmed_results(keyword, max_results=20):
    handle = Entrez.esearch(db="pubmed", term=keyword, retmax=max_results, sort='relevance')
    record = Entrez.read(handle)
    id_list = record["IdList"]
    summaries = []

    for pmid in id_list:
        handle = Entrez.efetch(db="pubmed", id=pmid, rettype="medline", retmode="xml")
        records = Entrez.read(handle)
        article_data = records["PubmedArticle"][0]
        article = article_data["MedlineCitation"]["Article"]
        journal_info = article.get("Journal", {}).get("JournalIssue", {})
        pub_date = journal_info.get("PubDate", {})
        article_ids = article_data.get("PubmedData", {}).get("ArticleIdList", [])

        title = article.get("ArticleTitle", "")
        authors = ", ".join(
            ["{} {}".format(a.get("ForeName", ""), a.get("LastName", "")) for a in article.get("AuthorList", [])]
        )
        year = pub_date.get("Year", "N/A")
        volume = journal_info.get("Volume", "N/A")
        issue = journal_info.get("Issue", "N/A")
        pages = article.get("Pagination", {}).get("MedlinePgn", "")
        article_number = article.get("ELocationID", [{}])[0].get("#text", "")

        pmid_final = next((i for i in article_ids if i.attributes["IdType"] == "pubmed"), pmid)
        doi = next((i for i in article_ids if i.attributes["IdType"] == "doi"), None)
        pdf_link = f"https://doi.org/{doi}" if doi else "N/A"

        abstract = article.get("Abstract", {}).get("AbstractText", [""])[0]
        summary = abstract[:300] + ("..." if len(abstract) > 300 else "")

        # Author keywords
        keyword_list = article_data["MedlineCitation"].get("KeywordList", [])
        author_keywords = ", ".join(keyword_list[0]) if keyword_list else "N/A"

        # MeSH terms
        mesh_list = article_data["MedlineCitation"].get("MeshHeadingList", [])
        mesh_terms = ", ".join([m["DescriptorName"] for m in mesh_list]) if mesh_list else "N/A"

        summaries.append({
            "Title": title,
            "Authors": authors,
            "Year": year,
            "Volume": volume,
            "Issue": issue,
            "Pages": pages or article_number or "N/A",
            "PMID": pmid_final,
            "PDF": pdf_link,
            "AuthorKeywords": author_keywords,
            "MeshTerms": mesh_terms,
            "Summary": summary
        })

    return summaries

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    keyword = ""
    if request.method == "POST":
        keyword = request.form["keyword"]
        results = fetch_pubmed_results(keyword)
    return render_template("index.html", results=results, keyword=keyword)

@app.route("/download", methods=["POST"])
def download():
    results = json.loads(request.form.get("csv_data", "[]"))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Title", "Authors", "Year", "Volume", "Issue", "Pages", "PMID", "PDF", "AuthorKeywords", "MeshTerms", "Summary"])
    for row in results:
        cw.writerow([row[k] for k in ["Title", "Authors", "Year", "Volume", "Issue", "Pages", "PMID", "PDF", "AuthorKeywords", "MeshTerms", "Summary"]])
    output = io.BytesIO()
    output.write(si.getvalue().encode("utf-8"))
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="pubmed_results.csv")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=True, host="0.0.0.0", port=port)
