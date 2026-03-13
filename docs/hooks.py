def on_page_markdown(markdown, page, config, files):
    if page.file.src_path == "README.md":
        page.meta["hide"] = ["navigation", "toc"]
    return markdown
