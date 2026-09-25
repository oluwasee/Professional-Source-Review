from urllib.parse import urlparse

import streamlit as st


st.set_page_config(
    page_title="Professional Source Review",
    page_icon="P",
    layout="centered",
)


def valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


st.title("Professional Source Review")
st.caption("A consent-based workspace for reviewing candidate-provided professional sources.")

st.info(
    "This demo does not scrape social-media platforms, classify sensitive traits, "
    "or make hiring recommendations. Review each source yourself and follow your "
    "local employment and privacy requirements."
)

with st.form("review_form"):
    first_name = st.text_input("First name")
    last_name = st.text_input("Last name")
    source_text = st.text_area(
        "Candidate-provided professional URLs",
        placeholder="Paste one URL per line, for example:\nhttps://example.com/profile",
        height=120,
    )
    consent = st.checkbox(
        "I confirm that the candidate has consented to this review.",
    )
    submitted = st.form_submit_button("Create review")

if submitted:
    first_name = first_name.strip()
    last_name = last_name.strip()
    urls = [line.strip() for line in source_text.splitlines() if line.strip()]
    invalid_urls = [url for url in urls if not valid_http_url(url)]

    if not first_name or not last_name:
        st.error("Enter both the first name and last name.")
    elif not consent:
        st.error("Candidate consent is required before creating a review.")
    elif invalid_urls:
        st.error("Each source must be a complete HTTP or HTTPS URL.")
        st.write("Invalid entries:", ", ".join(invalid_urls))
    else:
        st.session_state["review"] = {
            "name": f"{first_name} {last_name}",
            "urls": urls,
        }

review = st.session_state.get("review")
if review:
    st.divider()
    st.subheader(f"Review for {review['name']}")
    st.caption("Sources are shown exactly as provided. No automated conclusion is generated.")

    if not review["urls"]:
        st.warning("No professional URLs were provided.")
    else:
        for index, url in enumerate(review["urls"], start=1):
            st.write(f"{index}. [{url}]({url})")

    if st.button("Clear review"):
        del st.session_state["review"]
        st.rerun()