import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import bs4
import pandas as pd
import requests
import streamlit as st

# --- Core Crawler Functions ---


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


def get_domain_prefix(url):
    """Extracts clean domain name string to generate unique file export signatures."""
    try:
        parsed = urlparse(url.strip())
        domain = parsed.netloc if parsed.netloc else parsed.path
        domain = domain.replace("www.", "")
        clean_name = re.sub(r"[^\w\-_]", "_", domain)
        return clean_name.strip("_") if clean_name else "live_site"
    except Exception:
        return "live_site"


# --- Cache Management ---
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None
if "w1_count" not in st.session_state:
    st.session_state.w1_count = 0
if "w2_count" not in st.session_state:
    st.session_state.w2_count = 0
if "match_count" not in st.session_state:
    st.session_state.match_count = 0

# --- Advanced Adaptive SaaS Style Injector ---
st.set_page_config(
    page_title="Redesign SEO Migration Suite", page_icon="🔮", layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    /* Font Polish Across Global Container */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    /* Dynamic Gradient Heading Style */
    .dashboard-title {
        background: linear-gradient(135deg, #00C9A7 0%, #0052D4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        font-size: 2.6rem !important;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    
    .dashboard-subheading {
        color: var(--text-color) !important;
        opacity: 0.8;
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        margin-bottom: 4px;
        line-height: 1.4;
    }
    
    .brand-attribution {
        color: #00C9A7 !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 25px;
    }
    
    /* Modernized SaaS Cards for Metrics Block */
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(0, 201, 167, 0.2) !important;
        border-radius: 14px !important;
        padding: 20px 24px !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04) !important;
        border-color: rgba(0, 201, 167, 0.4) !important;
    }
    
    /* Unified Numeric Metrics Typography & High Contrast Styling */
    div[data-testid="stMetricValue"] {
        color: #0052D4 !important;
        font-weight: 800 !important;
        font-size: 2.8rem !important;
        letter-spacing: -1px;
    }
    
    /* Specific adjustment to prevent dark mode visibility washing out */
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetricValue"] {
            color: #00C9A7 !important;
        }
    }
    
    div[data-testid="stMetricLabel"] {
        color: var(--text-color) !important;
        opacity: 0.7;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* High Visibility Primary Run Audit Action Button Setup */
    button[aria-label="⚡ RUN MATCHING AUDIT"] {
        background: linear-gradient(135deg, #00C9A7 0%, #0052D4 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 28px !important;
        box-shadow: 0 10px 20px -10px rgba(0, 82, 212, 0.5) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    button[aria-label="⚡ RUN MATCHING AUDIT"]:hover {
        box-shadow: 0 20px 25px -10px rgba(0, 82, 212, 0.6) !important;
        transform: translateY(-1px);
        opacity: 0.95;
    }
    
    /* Secondary Download & Interface Action Buttons Configuration */
    div.stDownloadButton > button, button[aria-label="🔄 START AUDIT FOR NEW SITE"] {
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.25) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
        transition: all 0.2s ease !important;
    }
    div.stDownloadButton > button:hover, button[aria-label="🔄 START AUDIT FOR NEW SITE"]:hover {
        border-color: #00C9A7 !important;
        color: #00C9A7 !important;
        background-color: var(--secondary-background-color) !important;
    }
    
    /* Clean inputs design layout card block styles */
    .stTextInput > div {
        border-radius: 10px !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        background-color: var(--secondary-background-color) !important;
    }
    
    /* Elegant Expandable Info Boxes */
    div[data-testid="stExpander"] {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.15) !important;
        border-radius: 10px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Header Section
st.markdown(
    "<h1 class='dashboard-title'>🔮 Redesign SEO Migration Suite</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='dashboard-subheading'>Instantly scrape, map, and export complete live site SEO portfolios into clean RankMath configurations for your beta site.</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='brand-attribution'>POWERED BY GROWTH99</div>",
    unsafe_allow_html=True,
)

# Detailed Info Dropdown
with st.expander("ℹ️ About This Audit Engine & Workflow Pipeline", expanded=False):
    st.markdown(
        """
        ### What this application does:
        This application automates and speeds up the **SEO migration process during a website redesign**. It eliminates manual entry by scraping data from your old, live website and restructuring it into a clean blueprint format ready for bulk deployment on your new site.
        
        **Key Features & Workflow:**
        * **Automated URL Mapping:** Deep-scrapes sitemaps from both your **Current Live Site** and **Beta Site**, matching corresponding pages automatically using URL slugs.
        * **Full-Scale SEO Scraper:** Crawls the live site to gather **all production SEO meta-data** including Meta Titles, Meta Descriptions, Canonical Tags, Open Graph structures, and Schema JSON-LD blocks.
        * **RankMath Compatibility Export:** Packages all extracted metrics into a custom structured data sheet designed for WordPress imports, allowing you to bulk-upload and instantly deploy your entire SEO portfolio onto the new environment.
        """
    )

st.write("")

# Target Entry Panel
col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input(
        "Enter Current Live Site (Sitemap XML URL)",
        value="",
        placeholder="e.g., https://example.com/sitemap_index.xml",
    )
with col2:
    sitemap_2_input = st.text_input(
        "Enter Beta Site (Sitemap XML URL)",
        value="",
        placeholder="e.g., https://beta.example.com/sitemap_index.xml",
    )

st.write("")

# Centered Action Trigger Implementation Block
_, center_btn_col, _ = st.columns([2, 2, 2])
with center_btn_col:
    action_btn = st.button(
        "⚡ RUN MATCHING AUDIT", type="primary", use_container_width=True
    )

# Execution Logic Processing Window
if action_btn:
    if not sitemap_1_input.strip() or not sitemap_2_input.strip():
        st.error(
            "Execution parameters incomplete. Please fill out both sitemap address boxes to proceed."
        )
    elif sitemap_1_input.strip() == sitemap_2_input.strip():
        st.error(
            "🔄 Input Conflict: Both fields contain the exact same URL. Please enter your old live sitemap on the left and your beta sitemap on the right."
        )
    else:
        with st.spinner("Extracting deep index maps recursively..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error("Failed to parse targets. Confirm XML access privileges.")
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
                status_text.markdown(f"`Scanning Live Site:` **/{slug}**")
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
            st.toast("Verification Complete!", icon="✨")

# Presentation Panel View Layout
if st.session_state.audit_results is not None:
    st.write("---")

    # Balanced Analytics Metrics Row
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(label="Live Site Total URLs", value=st.session_state.w1_count)
    with m2:
        st.metric(label="Beta Site Total URLs", value=st.session_state.w2_count)
    with m3:
        st.metric(label="Matched Intersections", value=st.session_state.match_count)

    st.write("")

    st.dataframe(
        st.session_state.audit_results,
        use_container_width=True,
        hide_index=True,
    )

    st.write("")

    # Determine Domain Prefix Signature Name dynamically
    site_prefix = get_domain_prefix(sitemap_1_input)

    # Action Row Options Grid
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        csv_data = st.session_state.audit_results.to_csv(
            index=False, encoding="utf-8-sig"
        )
        st.download_button(
            label="📥 EXPORT MASTER DATA SHEET",
            data=csv_data,
            file_name=f"{site_prefix}_seo_migration_matrix.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with btn_col2:
        matched_df = st.session_state.audit_results[
            st.session_state.audit_results["Match Status"] == "MATCHED"
        ].copy()

        rankmath_complete_df = pd.DataFrame(
            {
                "url": matched_df["Beta Site Raw URL"],
                "title": matched_df["Meta Title (from Live)"],
                "description": matched_df["Meta Description (from Live)"],
                "canonical": matched_df["Canonical Tag (from Live)"],
                "og_metadata": matched_df["Open Graph Tags (from Live)"],
                "schema_markup": matched_df["Schema JSON-LD (from Live)"],
            }
        )

        rankmath_all_csv = rankmath_complete_df.to_csv(
            index=False, encoding="utf-8-sig"
        )
        st.download_button(
            label="📥 EXPORT RANKMATH ALL SEO DATA",
            data=rankmath_all_csv,
            file_name=f"{site_prefix}_rankmath_complete_seo_export.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with btn_col3:
        if st.button("🔄 START AUDIT FOR NEW SITE", use_container_width=True):
            st.session_state.audit_results = None
            st.session_state.w1_count = 0
            st.session_state.w2_count = 0
            st.session_state.match_count = 0
            st.rerun()
