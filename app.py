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
    """Extracts purely the clean path slug from any URL string, ignoring domains and trailing slashes."""
    if not url:
        return ""
    try:
        parsed_url = urlparse(url.strip())
        path = parsed_url.path
        slug = path.strip().strip("/").lower()
        return slug if slug else "homepage"
    except Exception:
        return ""


def extract_urls_from_sitemap_url(sitemap_url):
    """Deep parses sitemap XML data recursively.

    Follows nested <sitemap> tags down to individual page <url> tags.
    """
    urls = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(sitemap_url.strip(), headers=headers, timeout=15)
        if response.status_code != 200:
            return []

        # Strip any XML namespace declarations to ensure findall works cleanly
        xml_text = re.sub(r'\sxmlns="[^"]+"', "", response.text, count=1)
        root = ET.fromstring(xml_text.encode("utf-8"))

        # Case A: Nested Sitemap Index (<sitemap> tags found)
        sitemaps = root.findall(".//sitemap/loc")
        if sitemaps:
            for sitemap_node in sitemaps:
                if sitemap_node.text:
                    sub_url = sitemap_node.text.strip()
                    # Recursively go deeper into the sub-sitemaps
                    sub_urls = extract_urls_from_sitemap_url(sub_url)
                    urls.update(sub_urls)

        # Case B: Standard URL lists (<url> tags found)
        locs = root.findall(".//url/loc")
        for loc in locs:
            if loc.text:
                urls.add(loc.text.strip())

        return list(urls)
    except Exception:
        return []


def scrape_current_live_site_seo(url):
    """Crawls a target webpage on the Current Live Site to gather current SEO tags."""
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
st.set_page_config(
    page_title="SEO Sitemap Migration Matrix", page_icon="🗺️", layout="wide"
)

st.title("🗺️ Automated URL Slug-to-Slug SEO Mapper")
st.write(
    "Enter the exact sitemap XML addresses below. The engine will extract all nested links, pull the slugs, map them, and gather Current Live Site SEO data."
)

col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input(
        "Current Live Site Sitemap XML URL",
        "https://youthfulmedicine.com/sitemap_index.xml",
    )
with col2:
    sitemap_2_input = st.text_input(
        "Beta Site Sitemap XML URL",
        "https://youthfulmedicine.gogroth.com/sitemap_index.xml",
    )

if st.button("Extract Sitemaps, Match Slugs & Generate", type="primary"):
    if not sitemap_1_input or not sitemap_2_input:
        st.error("Please fill in both sitemap URL inputs.")
    else:
        with st.spinner("Step 1: Parsing deep sitemap indices recursively..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        # Show exactly how many URLs were uncovered from the sitemaps
        st.info(
            f"📋 Discovered {len(w1_urls)} URLs from Current Live Site and {len(w2_urls)} URLs from Beta Site."
        )

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error(
                "Could not extract any URLs. Please verify that both sitemap inputs are live XML addresses."
            )
        else:
            # Map Current Live Site URLs using their clean path slug as the lookup key
            w1_slug_to_url = {}
            for url in w1_urls:
                slug = get_slug_from_url(url)
                if slug:
                    w1_slug_to_url[slug] = url

            # Scrape Current Live Site pages for real-time SEO validation
            w1_seo_data = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, (slug, url) in enumerate(w1_slug_to_url.items()):
                status_text.text(
                    f"Scraping Current Live Site Metadata ({i+1}/{len(w1_slug_to_url)}): /{slug}"
                )
                seo = scrape_current_live_site_seo(url)
                if seo:
                    w1_seo_data[slug] = seo
                progress_bar.progress((i + 1) / len(w1_slug_to_url))

            status_text.text("Matching slug matrix arrays side-by-side...")

            # Build matrix rows driven by Beta Site's structure
            final_rows = []
            for idx, w2_url in enumerate(w2_urls, start=1):
                w2_slug = get_slug_from_url(w2_url)
                display_w2_slug = "/" if w2_slug == "homepage" else f"/{w2_slug}"

                if w2_slug in w1_slug_to_url:
                    w1_url = w1_slug_to_url[w2_slug]
                    display_w1_slug = display_w2_slug
                    match_status = "MATCHED"

                    # Collect scraped data profile
                    seo = w1_seo_data.get(w2_slug, None)
                    meta_title = seo["title"] if seo else ""
                    meta_desc = seo["meta_description"] if seo else ""
                    canonical = seo["canonical"] if seo else ""
                    og_tags = seo["og_tags"] if seo else ""
                    schema = seo["schema_json_ld"] if seo else ""
                else:
                    w1_url = "N/A"
                    display_w1_slug = "N/A"
                    match_status = "NO MATCH FOUND"
                    meta_title = "N/A"
                    meta_desc = "N/A"
                    canonical = "N/A"
                    og_tags = "N/A"
                    schema = "N/A"

                final_rows.append(
                    {
                        "#": idx,
                        "Current Live Site Slug": display_w1_slug,
                        "Beta Site Slug": display_w2_slug,
                        "Match Status": match_status,
                        "Current Live Site Raw URL": w1_url,
                        "Beta Site Raw URL": w2_url,
                        "Meta Title (from Live)": meta_title,
                        "Meta Description (from Live)": meta_desc,
                        "Canonical Tag (from Live)": canonical,
                        "Open Graph Tags (from Live)": og_tags,
                        "Schema JSON-LD (from Live)": schema,
                    }
                )

            df = pd.DataFrame(final_rows)
            progress_bar.empty()
            status_text.empty()

            st.success("🎉 Migration Mapping Complete!")
            st.dataframe(df, use_container_width=True)

            csv_data = df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 Download Structured CSV Matrix",
                data=csv_data,
                file_name="seo_migration_matrix.csv",
                mime="text/csv",
            )
