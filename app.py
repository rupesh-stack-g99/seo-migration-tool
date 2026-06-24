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
    """Deep parses sitemap XML data recursively to handle nested WordPress setups."""
    urls = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(sitemap_url.strip(), headers=headers, timeout=15)
        if response.status_code != 200:
            return []

        xml_text = re.sub(r'\sxmlns="[^"]+"', "", response.text, count=1)
        root = ET.fromstring(xml_text.encode("utf-8"))

        sitemaps = root.findall(".//sitemap/loc")
        if sitemaps:
            for sitemap_node in sitemaps:
                if sitemap_node.text:
                    sub_url = sitemap_node.text.strip()
                    sub_urls = extract_urls_from_sitemap_url(sub_url)
                    urls.update(sub_urls)

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


# --- Session State Handling ---
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "w1_count" not in st.session_state:
    st.session_state.w1_count = 0
if "w2_count" not in st.session_state:
    st.session_state.w2_count = 0
if "match_count" not in st.session_state:
    st.session_state.match_count = 0

# --- Advanced Dashboard UI Theme Styling ---
st.set_page_config(
    page_title="Enterprise SEO Migration Control Suite",
    page_icon="⚡",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #00FFCC !important; font-weight: 800 !important; letter-spacing: -1px; }
    .stButton>button {
        background-color: #00FFCC !important; color: #0E1117 !important;
        font-weight: 700 !important; border-radius: 8px !important;
        border: none !important; padding: 0.6rem 2rem !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,255,204,0.4); }
    div[data-testid="stMetricValue"] { color: #00FFCC !important; font-family: monospace; font-size: 2.2rem; }
    .status-card {
        background: #1E2633; padding: 20px; border-radius: 12px;
        border-left: 5px solid #00FFCC; margin-bottom: 20px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Header Section
st.title("⚡ Enterprise SEO Migration Suite")
st.markdown(
    "Automated deep mapping matrix connecting structural slug configurations with historical metadata alignments."
)

# Input Panel
with st.container():
    st.markdown(
        "<div class='status-card'><h4>Config Target Entry Endpoints</h4></div>",
        unsafe_allow_html=True,
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

    action_btn = st.button("Run Automated Alignment Audit", type="primary")

# Execution Engine
if action_btn:
    if not sitemap_1_input or not sitemap_2_input:
        st.error("Missing targeting parameters. Provide input to proceed.")
    else:
        with st.spinner("Processing deep target mapping indices recursively..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error(
                "Zero endpoint entities resolved. Verify sitemap configurations."
            )
        else:
            st.session_state.w1_count = len(w1_urls)
            st.session_state.w2_count = len(w2_urls)

            w1_slug_to_url = {}
            for url in w1_urls:
                slug = get_slug_from_url(url)
                if slug:
                    w1_slug_to_url[slug] = url

            w1_seo_data = {}
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, (slug, url) in enumerate(w1_slug_to_url.items()):
                status_text.markdown(
                    f"`Scraping Current Live Site:` **/{slug}**"
                )
                seo = scrape_current_live_site_seo(url)
                if seo:
                    w1_seo_data[slug] = seo
                progress_bar.progress((i + 1) / len(w1_slug_to_url))

            progress_bar.empty()
            status_text.empty()

            final_rows = []
            matched_counter = 0

            for idx, w2_url in enumerate(w2_urls, start=1):
                w2_slug = get_slug_from_url(w2_url)
                display_w2_slug = "/" if w2_slug == "homepage" else f"/{w2_slug}"

                if w2_slug in w1_slug_to_url:
                    w1_url = w1_slug_to_url[w2_slug]
                    display_w1_slug = display_w2_slug
                    match_status = "MATCHED"
                    matched_counter += 1

                    seo = w1_seo_data.get(w2_slug, None)
                    meta_title = seo["title"] if seo else ""
                    meta_desc = seo["meta_description"] if seo else ""
                    canonical = seo["canonical"] if seo else ""
                    og_tags = seo["og_tags"] if seo else ""
                    schema = seo["schema_json_ld"] if seo else ""
                else:
                    w1_url = "N/A"
                    display_w1_slug = "N/A"
                    match_status = "NO MATCH"
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

            st.session_state.match_count = matched_counter
            st.session_state.audit_results = pd.DataFrame(final_rows)
            st.success("🎉 Alignment Matrix successfully compiled!")

# Data Display Workspace
if st.session_state.audit_results is not None:
    st.write("---")

    # Real-Time Dashboard Analytics Cards
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(
            label="Live Site URLs Found", value=st.session_state.w1_count
        )
    with m2:
        st.metric(label="Beta Site URLs Found", value=st.session_state.w2_count)
    with m3:
        st.metric(label="Matched Slugs", value=st.session_state.match_count)

    st.write("")

    # High-Performance Data Matrix Presentation Panel
    st.dataframe(
        st.session_state.audit_results,
        use_container_width=True,
        hide_index=True,
    )

    st.write("")

    # Persistent Global Controller Panel
    ctrl_col1, ctrl_col2 = st.columns([1, 4])
    with ctrl_col1:
        csv_data = st.session_state.audit_results.to_csv(
            index=False, encoding="utf-8-sig"
        )
        st.download_button(
            label="📥 Export Clean CSV",
            data=csv_data,
            file_name="seo_migration_matrix.csv",
            mime="text/csv",
        )
    with ctrl_col2:
        if st.button("🔄 Reset Suite / Rerun New Audit"):
            st.session_state.audit_results = None
            st.session_state.w1_count = 0
            st.session_state.w2_count = 0
            st.session_state.match_count = 0
            st.rerun()
