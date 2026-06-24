import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import bs4
import pandas as pd
import requests
import streamlit as st

# --- Helper Functions ---


def get_slug(url):
    path = urlparse(url).path
    return path.strip("/").lower()


def discover_urls_from_sitemap(domain_url):
    urls = set()
    sitemap_locations = ["sitemap.xml", "sitemap_index.xml", "wp-sitemap.xml"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for loc in sitemap_locations:
        sitemap_url = urljoin(domain_url, loc)
        try:
            response = requests.get(sitemap_url, headers=headers, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                namespaces = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

                sub_sitemaps = root.findall(".//ns:sitemap/ns:loc", namespaces)
                if sub_sitemaps:
                    for sub in sub_sitemaps:
                        sub_res = requests.get(
                            sub.text, headers=headers, timeout=10
                        )
                        if sub_res.status_code == 200:
                            sub_root = ET.fromstring(sub_res.content)
                            for loc_tag in sub_root.findall(
                                ".//ns:url/ns:loc", namespaces
                            ):
                                urls.add(loc_tag.text.strip())
                else:
                    for loc_tag in root.findall(".//ns:url/ns:loc", namespaces):
                        urls.add(loc_tag.text.strip())
                if urls:
                    return list(urls)
        except Exception:
            continue
    return [domain_url]


def scrape_website_1_seo(url, status_container):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        soup = bs4.BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else ""
        desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = desc_tag["content"].strip() if desc_tag else ""
        canonical_tag = soup.find("link", rel="canonical")
        canonical = canonical_tag["href"].strip() if canonical_tag else ""

        og_tags = {}
        for tag in soup.find_all("meta", property=re.compile(r"^og:")):
            og_tags[tag["property"]] = tag.get("content", "").strip()

        schemas = []
        schema_tags = soup.find_all("script", type="application/ld+json")
        for tag in schema_tags:
            try:
                if tag.string:
                    schemas.append(json.loads(tag.string.strip()))
            except Exception:
                schemas.append(tag.string.strip() if tag.string else "")

        return {
            "slug": get_slug(url),
            "w1_url": url,
            "title": title,
            "meta_description": meta_desc,
            "canonical": canonical,
            "og_tags": json.dumps(og_tags, ensure_ascii=False),
            "schema_json_ld": json.dumps(schemas, ensure_ascii=False),
        }
    except Exception:
        return None


# --- Streamlit UI App ---
st.set_page_config(page_title="SEO Migration Mapper", page_icon="🔗", layout="wide")

st.title("🔗 Domain-to-Domain SEO Migration Mapper")
st.write(
    "Enter your old and new domain URLs. The tool will automatically find the pages via sitemaps, scrape Website 1's SEO metrics, map them by slug, and build a CSV download."
)

col1, col2 = st.columns(2)
with col1:
    domain_1 = st.text_input(
        "Website 1 (Source Domain)", "https://example-website1.com"
    )
with col2:
    domain_2 = st.text_input(
        "Website 2 (Destination Domain)", "https://example-website2.com"
    )

if st.button("Generate Migration Sheet", type="primary"):
    if not domain_1 or not domain_2:
        st.error("Please provide both domain URLs.")
    else:
        with st.spinner("Step 1: Discovering URLs via Sitemaps..."):
            w1_urls = discover_urls_from_sitemap(domain_1)
            w2_urls = discover_urls_from_sitemap(domain_2)

        st.info(
            f"Found {len(w1_urls)} URLs on Website 1 and {len(w2_urls)} URLs on Website 2."
        )

        w1_data_store = {}
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 2: Scrape Website 1
        for i, url in enumerate(w1_urls):
            status_text.text(f"Scraping Website 1 ({i+1}/{len(w1_urls)}): {url}")
            data = scrape_website_1_seo(url, status_text)
            if data:
                w1_data_store[data["slug"]] = data
            progress_bar.progress((i + 1) / len(w1_urls))

        status_text.text("Mapping layouts and compiling CSV...")

        # Step 3: Map to Website 2
        final_rows = []
        for w2_url in w2_urls:
            slug = get_slug(w2_url)
            if slug in w1_data_store:
                w1_info = w1_data_store[slug]
                final_rows.append(
                    {
                        "Match Status": "MATCHED",
                        "Slug": slug,
                        "Website 2 New URL": w2_url,
                        "Website 1 Old URL": w1_info["w1_url"],
                        "Meta Title": w1_info["title"],
                        "Meta Description": w1_info["meta_description"],
                        "Canonical (Old)": w1_info["canonical"],
                        "Open Graph Tags": w1_info["og_tags"],
                        "Schema JSON-LD": w1_info["schema_json_ld"],
                    }
                )
            else:
                final_rows.append(
                    {
                        "Match Status": "NO MATCH FOUND",
                        "Slug": slug,
                        "Website 2 New URL": w2_url,
                        "Website 1 Old URL": "N/A",
                        "Meta Title": "",
                        "Meta Description": "",
                        "Canonical (Old)": "",
                        "Open Graph Tags": "",
                        "Schema JSON-LD": "",
                    }
                )

        df = pd.DataFrame(final_rows)
        progress_bar.empty()
        status_text.empty()

        st.success("🎉 Migration Mapping Sheet Generated!")

        # Display a preview of the mapping data
        st.dataframe(df.head(10))

        # Convert dataframe to CSV byte stream for downloading
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")

        st.download_button(
            label="📥 Download Complete CSV Sheet",
            data=csv_data,
            file_name="seo_migration_mapping.csv",
            mime="text/csv",
        )
