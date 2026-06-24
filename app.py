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
    """Extracts purely the clean path slug from any URL string, ignoring the domain name."""
    if not url:
        return ""
    parsed_url = urlparse(url)
    path = parsed_url.path
    slug = path.strip().strip("/").lower()
    return slug if slug else "homepage"


def extract_urls_from_sitemap_url(sitemap_url):
    """Fetches and reads all URLs from a sitemap link, handling sub-sitemaps automatically."""
    urls = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(sitemap_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []

        # Strip namespace to ensure element tags parse easily
        xml_data = re.sub(r'\sxmlns="[^"]+"', "", response.text, count=1)
        root = ET.fromstring(xml_data.encode("utf-8"))

        # Look for nested sitemap indices
        sitemaps = root.findall(".//sitemap/loc")
        if sitemaps:
            for sitemap_node in sitemaps:
                sub_url = sitemap_node.text.strip()
                sub_urls = extract_urls_from_sitemap_url(sub_url)
                urls.update(sub_urls)

        # Look for direct page URLs
        locs = root.findall(".//url/loc")
        for loc in locs:
            if loc.text:
                urls.add(loc.text.strip())

        return list(urls)
    except Exception:
        return []


def scrape_website_1_seo(url):
    """Crawls a single URL on Website 1 to scrape its live SEO elements."""
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


# --- Streamlit Layout ---
st.set_page_config(page_title="SEO Migration Mapper", page_icon="🗺️", layout="wide")

st.title("🗺️ Automated URL Slug-to-Slug SEO Mapper")
st.write(
    "Paste the sitemap links below. The tool will parse all full URLs, strip them down to **pure slugs**, match them up, and transfer Website 1's SEO metrics."
)

col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input(
        "Website 1 (Main Live Sitemap XML URL)",
        "https://youthfulmedicine.com/sitemap.xml",
    )
with col2:
    sitemap_2_input = st.text_input(
        "Website 2 (Beta Website Sitemap XML URL)",
        "https://youthfulmedicine.gogroth.com/sitemap.xml",
    )

if st.button("Extract, Match Slugs & Generate Sheet", type="primary"):
    if not sitemap_1_input or not sitemap_2_input:
        st.error("Please fill out both sitemap address fields.")
    else:
        with st.spinner("Step 1: Extracting URLs from both sitemaps..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        st.info(
            f"📋 Pulled {len(w1_urls)} URLs from Website 1 and {len(w2_urls)} URLs from Website 2."
        )

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error(
                "Could not parse any URLs. Verify that both sitemap URLs are fully functional XML paths."
            )
        else:
            # Step 2: Extract data from Website 1 and map it by its pure slug
            w1_data_store = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, url in enumerate(w1_urls):
                slug = get_slug_from_url(url)
                status_text.text(
                    f"Scraping Website 1 Data for Slug ({i+1}/{len(w1_urls)}): /{slug}"
                )

                seo_info = scrape_website_1_seo(url)
                if seo_info:
                    w1_data_store[slug] = seo_info
                progress_bar.progress((i + 1) / len(w1_urls))

            status_text.text("Compiling comparison matrix...")

            # Step 3: Match Website 2 slugs against Website 1 slugs
            final_rows = []
            for w2_url in w2_urls:
                slug = get_slug_from_url(w2_url)
                display_slug = "/" if slug == "homepage" else f"/{slug}"

                if slug in w1_data_store:
                    w1_seo = w1_data_store[slug]
                    final_rows.append(
                        {
                            "Match Status": "MATCHED",
                            "Website 2 Slug": display_slug,
                            "Website 1 Slug": display_slug,
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
                            "Match Status": "NO MATCH FOUND",
                            "Website 2 Slug": display_slug,
                            "Website 1 Slug": "N/A",
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

            st.success("🎉 Migration Mapping Sheet Compiled!")
            st.dataframe(df, use_container_width=True)

            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Download Data Mapping CSV",
                data=csv_data,
                file_name="seo_migration_matrix.csv",
                mime="text/csv",
            )
