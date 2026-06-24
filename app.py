import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import bs4
import pandas as pd
import requests
import streamlit as st

# --- Helper Functions ---

def get_slug_from_url(url):
    """Extracts purely the clean path slug from any URL, ignoring domain and trailing slashes."""
    if not url:
        return ""
    parsed_url = urlparse(url)
    path = parsed_url.path
    # Lowercase, strip spaces, strip outer slashes
    slug = path.strip().strip("/").lower()
    return slug if slug else "homepage"

def extract_urls_from_sitemap_url(sitemap_url):
    """Fetches and reads a sitemap or a nested sitemap index recursively."""
    urls = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []

        # Parse XML Content safely
        xml_content = response.content
        root = ET.fromstring(xml_content)
        
        # Sitemaps use namespaces; we need to extract them or handle them
        # This regex removes namespace prefixes to make parsing foolproof
        xml_data = re.sub(r'\sxmlns="[^"]+"', '', response.text, count=1)
        root = ET.fromstring(xml_data.encode('utf-8'))

        # Check if it's a Sitemap Index (contains nested <sitemap> tags)
        sitemaps = root.findall(".//sitemap/loc")
        if sitemaps:
            for sitemap_node in sitemaps:
                sub_url = sitemap_node.text.strip()
                # Recursively fetch nested sitemaps
                sub_urls = extract_urls_from_sitemap_url(sub_url)
                urls.update(sub_urls)
        
        # Check for direct page URLs (<url> tags)
        locs = root.findall(".//url/loc")
        for loc in locs:
            if loc.text:
                urls.add(loc.text.strip())

        return list(urls)

    except Exception as e:
        return []

def scrape_website_1_seo(url):
    """Scrapes the live production site's metadata."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=12)
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
            "title": title,
            "meta_description": meta_desc,
            "canonical": canonical,
            "og_tags": json.dumps(og_tags, ensure_ascii=False),
            "schema_json_ld": json.dumps(schemas, ensure_ascii=False),
        }
    except Exception:
        return None


# --- Streamlit UI Layout ---
st.set_page_config(page_title="Sitemap SEO Migration Mapper", page_icon="🗺️", layout="wide")

st.title("🗺️ Pure Slug-to-Slug SEO Migration Mapper")
st.write("This tool extracts **only the clean slugs** from both sitemaps and completely ignores the domain names when running the comparison matching logic.")

col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input("Website 1 (Main Live Sitemap XML URL)", "https://youthfulmedicine.com/sitemap.xml")
with col2:
    sitemap_2_input = st.text_input("Website 2 (Beta Website Sitemap XML URL)", "https://youthfulmedicine.gogroth.com/sitemap.xml")

if st.button("Generate Migration Sheet from Sitemaps", type="primary"):
    if not sitemap_1_input or not sitemap_2_input:
        st.error("Please enter both sitemap link endpoints.")
    else:
        with st.spinner("Extracting index URLs from sitemaps..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        # Debug logs directly on the interface
        st.info(f"📋 URLs extracted from Live Sitemap (Website 1): {len(w1_urls)}")
        st.info(f"📋 URLs extracted from Beta Sitemap (Website 2): {len(w2_urls)}")

        if len(w1_urls) == 0:
            st.error("❌ Crucial Error: Website 1 sitemap returned 0 pages! Please ensure the URL is a valid XML file and is public.")
        elif len(w2_urls) == 0:
            st.error("❌ Crucial Error: Website 2 sitemap returned 0 pages!")
        else:
            # Step 1: Map Website 1 by pure slug
            w1_data_store = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, url in enumerate(w1_urls):
                slug = get_slug_from_url(url)
                status_text.text(f"Scraping Live SEO content for pure slug: {slug}")
                
                seo_info = scrape_website_1_seo(url)
                if seo_info:
                    w1_data_store[slug] = {
                        "w1_url": url,
                        **seo_info
                    }
                progress_bar.progress((i + 1) / len(w1_urls))

            status_text.text("Cross-matching structures...")

            # Step 2: Look up Website 2 pages by pure slug mapping
            final_rows = []
            for w2_url in w2_urls:
                slug = get_slug_from_url(w2_url)

                if slug in w1_data_store:
                    w1_info = w1_data_store[slug]
                    final_rows.append({
                        "Match Status": "MATCHED",
                        "Pure Slug": slug,
                        "Website 2 New URL (Beta)": w2_url,
                        "Website 1 Old URL (Live)": w1_info["w1_url"],
                        "Meta Title": w1_info["title"],
                        "Meta Description": w1_info["meta_description"],
                        "Canonical (Old)": w1_info["canonical"],
                        "Open Graph Tags": w1_info["og_tags"],
                        "Schema JSON-LD": w1_info["schema_json_ld"]
                    })
                else:
                    final_rows.append({
                        "Match Status": "NO MATCH FOUND",
                        "Pure Slug": slug,
                        "Website 2 New URL (Beta)": w2_url,
                        "Website 1 Old URL (Live)": "N/A",
                        "Meta Title": "",
                        "Meta Description": "",
                        "Canonical (Old)": "",
                        "Open Graph Tags": "",
                        "Schema JSON-LD": ""
                    })

            df = pd.DataFrame(final_rows)
            progress_bar.empty()
            status_text.empty()

            st.success("🎉 Cross-Matching Sheet Compiled Successfully!")
            st.dataframe(df)

            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Download Complete CSV Sheet",
                data=csv_data,
                file_name="seo_migration_mapping.csv",
                mime="text/csv",
            )
