from bs4 import BeautifulSoup


def clean_html(text):
    if not isinstance(text, str):
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator="\n").strip()