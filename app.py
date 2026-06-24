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
    """Extracts purely the clean path slug from any URL, ignoring the domain."""
    if not url:
        return ""
    parsed_url = urlparse(url)
    path = parsed_url.path
    slug = path.strip().strip("/").lower()
    return slug if slug else "homepage"


def extract_urls_from_sitemap_url(sitemap_url):
    """Fetches and reads all URLs from a sitemap, handling nested indexes automatically."""
    urls = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []

        # Remove XML namespaces dynamically to make standard tag parsing foolproof
        xml_data = re.sub(r'\sxmlns="[^"]+"', "", response.text, count=1)
        root = ET.fromstring(xml_data.encode("utf-8"))

        # Case A: Nested Sitemap Index (<sitemap> tags)
        sitemaps = root.findall(".//sitemap/loc")
        if sitemaps:
            for sitemap_node in sitemaps:
                sub_url = sitemap_node.text.strip()
                sub_urls = extract_urls_from_sitemap_url(sub_url)
                urls.update(sub_urls)

        # Case B: Direct Page List (<url> tags)
        locs = root.findall(".//url/loc")
        for loc in locs:
            if loc.text:
                urls.add(loc.text.strip())

        return list(urls)
    except Exception:
        return []


def scrape_website_1_seo(url):
    """Crawls a single page on Website 1 to scrape its live SEO metrics."""
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


# --- Streamlit Layout Configuration ---
st.set_page_config(page_title="SEO Migration Mapper", page_icon="🗺️", layout="wide")

st.title("🗺️ Automated URL Slug-to-Slug SEO Mapper")
st.write(
    "Paste the direct **Sitemap XML paths** below. The tool will parse the full links, strip them down to pure slugs, and cross-match them."
)

col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input(
        "Website 1 Sitemap XML URL (Main Live Site)",
        "https://youthfulmedicine.com/sitemap.xml",
    )
with col2:
    sitemap_2_input = st.text_input(
        "Website 2 Sitemap XML URL (Beta Site)",
        "https://youthfulmedicine.gogroth.com/sitemap.xml",
    )

if st.button("Extract, Match Slugs & Generate Sheet", type="primary"):
    if not sitemap_1_input or not sitemap_2_input:
        st.error("Please enter both sitemap XML addresses.")
    else:
        with st.spinner("Extracting active target URLs from sitemaps..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        st.info(
            f"📋 Loaded {len(w1_urls)} URLs from Website 1 and {len(w2_urls)} URLs from Website 2."
        )

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error(
                "Failed to pull data. Ensure you pasted a working sitemap link endpoint that contains valid XML metrics."
            )
        else:
            # Step 1: Scrape and index Website 1 by its pure slug
            w1_data_store = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, url in enumerate(w1_urls):
                slug = get_slug_from_url(url)
                status_text.text(
                    f"Scraping Website 1 Metadata ({i+1}/{len(w1_urls)}): /{slug}"
                )

                seo_info = scrape_website_1_seo(url)
                if seo_info:
                    w1_data_store[slug] = seo_info
                progress_bar.progress((i + 1) / len(w1_urls))

            status_text.text("Building layout dataframe alignment matrix...")

            # Step 2: Loop through Website 2 pages, match by slugs, and organize structural data columns
            final_rows = []
            for idx, w2_url in enumerate(w2_urls, start=1):
                slug = get_slug_from_url(w2_url)
                display_slug = "/" if slug == "homepage" else f"/{slug}"

                if slug in w1_data_store:
                    w1_seo = w1_data_store[slug]
                    final_rows.append(
                        {
                            "#": idx,
                            "Website 1 Slug (Live)": display_slug,
                            "Website 2 Slug (Beta)": display_slug,
                            "Match Status": "MATCHED",
                            "Meta Title (from W1)": w1_seo["title"],
                            "Meta Description (from W1)": w1_seo["meta_description"],
                            "Canonical Tag (from W1)": w1_seo["canonical"],
                            "Open Graph Tags (from W1)": w1_seo["og_tags"],
                            "Schema JSON-LD (from W1)": w1_seo["schema_json_ld"],
                        }
                    )
                else:
                    final_rows.append(
                        {
                            "#": idx,
                            "Website 1 Slug (Live)": "N/A",
                            "Website 2 Slug (Beta)": display_slug,
                            "Match Status": "NO MATCH FOUND",
                            "Meta Title (from W1)": "N/A",
                            "Meta Description (from W1)": "N/A",
                            "Canonical Tag (from W1)": "N/A",
                            "Open Graph Tags (from W1)": "N/A",
                            "Schema JSON-LD (from W1)": "N/A",
                        }
                    )

            df = pd.DataFrame(final_rows)
            progress_bar.empty()
            status_text.empty()

            st.success("🎉 Migration Mapping Sheet Generated!")

            # Render data matrix explicitly in your UI view window
            st.dataframe(df, use_container_width=True)

            # Export structured data arrays directly into file download streams
            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Download Data Mapping CSV",
                data=csv_data,
                file_name="seo_migration_matrix.csv",
                mime="text/csv",
            )
