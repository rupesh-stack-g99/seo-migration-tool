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
    """Crawls a target webpage to gather all standard, Facebook, and Twitter SEO tags."""
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

        # Extract Meta Keywords
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        keywords = keywords_tag["content"].strip() if keywords_tag else ""

        # Extract Social Meta Tags (Facebook & Twitter)
        social_tags = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property", "")
            name = tag.get("name", "")
            key = prop if prop else name
            if key.startswith("og:") or key.startswith("twitter:"):
                social_tags[key] = tag.get("content", "").strip()

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
            "keywords": keywords,
            "schema_json_ld": json.dumps(schemas, ensure_ascii=False),
            "fb_title": social_tags.get("og:title", title),
            "fb_desc": social_tags.get("og:description", meta_desc),
            "fb_image": social_tags.get("og:image", ""),
            "tw_title": social_tags.get("twitter:title", title),
            "tw_desc": social_tags.get("twitter:description", meta_desc),
            "tw_image": social_tags.get("twitter:image", ""),
        }
    except Exception:
        return None


def extract_wordpress_page_id(url):
    """Dual-Engine dynamic discovery system. Falls back to WP-JSON API endpoints to guarantee ID capture."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = bs4.BeautifulSoup(response.text, "html.parser")

            # Engine A1: Parse Target Body Classes
            body = soup.find("body")
            if body and body.has_attr("class"):
                classes = " ".join(body["class"])
                match = re.search(
                    r"(?:page-id-|postid-|id-)(\d+)", classes, re.IGNORECASE
                )
                if match:
                    return match.group(1)

            # Engine A2: Parse Rel Shortlinks
            shortlink = soup.find("link", rel="shortlink")
            if shortlink and shortlink.has_attr("href"):
                match = re.search(r"[?&](?:p|page_id)=(\d+)", shortlink["href"])
                if match:
                    return match.group(1)

        # Engine B: Deep REST API Engine Query Fallback (Uses Slugs to request matching database object ids directly)
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        slug = get_slug_from_url(url)

        if slug == "homepage":
            # Direct challenge query lookup for home instance variables
            api_url = f"{base_domain}/wp-json/wp/v2/pages?per_page=1"
        else:
            # Post/Page slug context filter lookup loop
            api_url = f"{base_domain}/wp-json/wp/v2/pages?slug={slug}"

        api_res = requests.get(api_url, headers=headers, timeout=8)
        if api_res.status_code == 200:
            data = api_res.json()
            if data and isinstance(data, list) and len(data) > 0:
                return str(data[0].get("id", ""))

        # CPT Fallback Check loop
        if slug != "homepage":
            cpt_api_url = f"{base_domain}/wp-json/wp/v2/posts?slug={slug}"
            cpt_res = requests.get(cpt_api_url, headers=headers, timeout=8)
            if cpt_res.status_code == 200:
                data = cpt_res.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return str(data[0].get("id", ""))

        return ""
    except Exception:
        return ""


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

# --- Interface Design Custom Styling Injector ---
st.set_page_config(
    page_title="Redesign SEO Migration Suite", page_icon="🔮", layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght=400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
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
    }
    
    .brand-attribution {
        color: #00C9A7 !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 25px;
    }
    
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(0, 201, 167, 0.2) !important;
        border-radius: 14px !important;
        padding: 20px 24px !important;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05) !important;
    }
    
    div[data-testid="stMetricValue"] {
        color: #0052D4 !important;
        font-weight: 800 !important;
        font-size: 2.8rem !important;
    }
    
    @media (prefers-color-scheme: dark) {
        div[data-testid="stMetricValue"] {
            color: #00C9A7 !important;
        }
    }
    
    button[aria-label="⚡ RUN MATCHING AUDIT"] {
        background: linear-gradient(135deg, #00C9A7 0%, #0052D4 100%) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 28px !important;
        box-shadow: 0 10px 20px -10px rgba(0, 82, 212, 0.5) !important;
    }
    
    div.stDownloadButton > button, button[aria-label="🔄 START AUDIT FOR NEW SITE"] {
        background-color: var(--background-color) !important;
        color: var(--text-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.25) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

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

with st.expander("ℹ️ About This Audit Engine & Workflow Pipeline"):
    st.markdown(
        "Automates mapping and metadata harvesting targets across platform architectures."
    )

col1, col2 = st.columns(2)
with col1:
    sitemap_1_input = st.text_input(
        "Enter Current Live Site (Sitemap XML URL)", value=""
    )
with col2:
    sitemap_2_input = st.text_input("Enter Beta Site (Sitemap XML URL)", value="")

_, center_btn_col, _ = st.columns([2, 2, 2])
with center_btn_col:
    action_btn = st.button(
        "⚡ RUN MATCHING AUDIT", type="primary", use_container_width=True
    )

if action_btn:
    if not sitemap_1_input.strip() or not sitemap_2_input.strip():
        st.error("Execution parameters incomplete.")
    else:
        with st.spinner("Processing deep indexing & harvesting properties..."):
            w1_urls = extract_urls_from_sitemap_url(sitemap_1_input.strip())
            w2_urls = extract_urls_from_sitemap_url(sitemap_2_input.strip())

        if len(w1_urls) == 0 or len(w2_urls) == 0:
            st.error("Failed to parse configurations safely.")
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
                status_text.markdown(f"`Scanning Live Site Engine:` **/{slug}**")
                seo = scrape_current_live_site_seo(url)
                if seo:
                    w1_seo_data[slug] = seo
                progress_bar.progress((i + 1) / len(w1_slug_to_url))

            progress_bar.empty()
            status_text.empty()

            final_rows = []
            matched_counter = 0

            beta_progress = st.progress(0)
            beta_status = st.empty()

            for idx, w2_url in enumerate(w2_urls, start=1):
                w2_slug = get_slug_from_url(w2_url)
                display_w2_slug = "/" if w2_slug == "homepage" else f"/{w2_slug}"
                beta_status.markdown(
                    f"`Fetching Beta WordPress Metadata:` **{display_w2_slug}**"
                )

                # Upgraded dual-engine call routine
                wp_page_id = extract_wordpress_page_id(w2_url)

                if w2_slug in w1_slug_to_url:
                    w1_url = w1_slug_to_url[w2_slug]
                    display_w1_slug = display_w2_slug
                    match_status = "MATCHED"
                    matched_counter += 1

                    seo = w1_seo_data.get(w2_slug, None)
                    meta_title = seo["title"] if seo else ""
                    meta_desc = seo["meta_description"] if seo else ""
                    canonical = seo["canonical"] if seo else ""
                    keywords = seo["keywords"] if seo else ""
                    schema = seo["schema_json_ld"] if seo else ""

                    fb_title = seo["fb_title"] if seo else ""
                    fb_desc = seo["fb_desc"] if seo else ""
                    fb_image = seo["fb_image"] if seo else ""
                    tw_title = seo["tw_title"] if seo else ""
                    tw_desc = seo["tw_desc"] if seo else ""
                    tw_image = seo["tw_image"] if seo else ""
                else:
                    w1_url = "N/A"
                    display_w1_slug = "N/A"
                    match_status = "NO MATCH"
                    meta_title, meta_desc, canonical, keywords, schema = (
                        "",
                        "",
                        "",
                        "",
                        "",
                    )
                    fb_title, fb_desc, fb_image, tw_title, tw_desc, tw_image = (
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    )

                final_rows.append(
                    {
                        "#": idx,
                        "Beta WP Page ID": wp_page_id,
                        "Current Live Site Slug": display_w1_slug,
                        "Beta Site Slug": display_w2_slug,
                        "Match Status": match_status,
                        "Meta Tags / Keywords": keywords,
                        "Current Live Site Raw URL": w1_url,
                        "Beta Site Raw URL": w2_url,
                        "Meta Title (from Live)": meta_title,
                        "Meta Description (from Live)": meta_desc,
                        "Canonical Tag (from Live)": canonical,
                        "Schema JSON-LD": schema,
                        "fb_title": fb_title,
                        "fb_desc": fb_desc,
                        "fb_image": fb_image,
                        "tw_title": tw_title,
                        "tw_desc": tw_desc,
                        "tw_image": tw_image,
                    }
                )
                beta_progress.progress((idx) / len(w2_urls))

            beta_progress.empty()
            beta_status.empty()

            st.session_state.match_count = matched_counter
            st.session_state.audit_results = pd.DataFrame(final_rows)
            st.toast("Verification Complete!", icon="✨")

if st.session_state.audit_results is not None:
    st.write("---")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric(label="Live Site Total URLs", value=st.session_state.w1_count)
    with m2:
        st.metric(label="Beta Site Total URLs", value=st.session_state.w2_count)
    with m3:
        st.metric(label="Matched Intersections", value=st.session_state.match_count)

    st.write("")
    st.dataframe(
        st.session_state.audit_results, use_container_width=True, hide_index=True
    )

    st.write("")
    site_prefix = get_domain_prefix(sitemap_1_input)
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

        # RankMath CSV Layout Array Output
        rankmath_complete_df = pd.DataFrame(
            {
                "id": matched_df["Beta WP Page ID"],
                "object_type": "post",
                "slug": matched_df["Beta Site Slug"].str.strip("/"),
                "seo_title": matched_df["Meta Title (from Live)"],
                "seo_description": matched_df["Meta Description (from Live)"],
                "is_pillar_content": 0,
                "focus_keyword": matched_df["Meta Tags / Keywords"],
                "seo_score": 80,  # Explicitly assigned default target score value
                "robots": "",
                "advanced_canonical": matched_df["Canonical Tag (from Live)"],
                "primary_term": "",
                "schema_data": matched_df["Schema JSON-LD"],
                "social_facebook_title": matched_df["fb_title"],
                "social_facebook_description": matched_df["fb_desc"],
                "social_facebook_image": matched_df["fb_image"],
                "social_twitter_title": matched_df["tw_title"],
                "social_twitter_image": matched_df["tw_image"],
                "social_twitter_description": matched_df["tw_desc"],
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
