/* Read bibliography markup without guessing a paper identity from its title. */
(() => {
  const idPattern = /^(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})$/;
  const clean = (text) => (text || "").replace(/\s+/g, " ").trim();
  function safeUrl(value, base) {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const url = new URL(value, base);
      return ["https:", "http:"].includes(url.protocol) ? url.href : null;
    } catch {
      return null;
    }
  }
  function paperId(value) {
    const id = value?.replace(/\.pdf$/i, "").replace(/v\d+$/, "");
    return idPattern.test(id) ? id : null;
  }
  function parse(entry, base) {
    const reference = clean(entry.textContent);
    const documentUrl = new URL(base);
    const links = [...entry.querySelectorAll("a[href]")]
      .map((a) => safeUrl(a.getAttribute("href"), base))
      .filter((href) => {
        if (!href) return false;
        const url = new URL(href);
        // Bibliography labels and back-links resolve to this HTML paper. They
        // navigate within the document; they do not identify the cited work.
        return (
          url.origin !== documentUrl.origin ||
          url.pathname !== documentUrl.pathname
        );
      });
    let id = null;
    for (const href of links) {
      const url = new URL(href);
      const host = url.hostname.toLowerCase();
      if (
        [
          "arxiv.org",
          "www.arxiv.org",
          "export.arxiv.org",
          "ar5iv.labs.arxiv.org",
        ].includes(host)
      ) {
        let pathname = url.pathname;
        try {
          pathname = decodeURIComponent(pathname);
        } catch {}
        id = paperId(pathname.match(/^\/(?:abs|pdf|html)\/(.+?)\/?$/)?.[1]);
      } else if (["doi.org", "dx.doi.org"].includes(host)) {
        id = paperId(url.pathname.match(/^\/10\.48550\/arxiv\.(.+)$/i)?.[1]);
      }
      if (id) break;
    }
    if (!id)
      id = paperId(
        reference.match(
          /arXiv\s*(?::|preprint\s+)?\s*((?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})(?:v\d+)?)/i,
        )?.[1],
      );
    const blocks = [...entry.querySelectorAll(".ltx_bibblock")]
      .map((node) => clean(node.textContent))
      .filter(Boolean);
    const field = (selector) =>
      clean(entry.querySelector(selector)?.textContent);
    let title = field('.ltx_bib_title, .bib-title, [itemprop="name"]');
    let authors = field('.ltx_bib_author, .bib-author, [itemprop="author"]');
    let publication = field(
      '.ltx_bib_journal, .ltx_bib_booktitle, [itemprop="isPartOf"]',
    );
    // LaTeXML usually separates authors, title, and publication into bibblocks.
    // Keep uncertain single-block references intact rather than split on initials.
    if (
      !title &&
      blocks.length >= 3 &&
      !/^(?:in\s|doi\s*:|https?:|arxiv\s*:)/i.test(blocks[1])
    ) {
      title = blocks[1];
      authors ||= blocks[0].replace(/^\[\d+\]\s*/, "");
      publication ||= blocks.slice(2).join(" ");
    }
    if (!title) title = reference.match(/[“"]([^“”"]{12,})[”"]/)?.[1] || "";
    const year = reference.match(/\b(?:19|20)\d{2}\b/)?.[0] || "";
    const doi = reference
      .match(/\b10\.\d{4,9}\/[^\s<>]+/i)?.[0]
      ?.replace(/[.,;]+$/, "");
    const url =
      links.find((href) =>
        ["doi.org", "dx.doi.org"].includes(new URL(href).hostname),
      ) ||
      links[0] ||
      (doi ? `https://doi.org/${doi}` : null);
    return {
      id,
      reference,
      details: {
        title,
        authors,
        publication,
        year,
        url,
        doi:
          doi ||
          links
            .map((href) => {
              const u = new URL(href);
              if (!["doi.org", "dx.doi.org"].includes(u.hostname)) return "";
              try {
                return decodeURIComponent(u.pathname.slice(1));
              } catch {
                return "";
              }
            })
            .find(Boolean) ||
          "",
      },
    };
  }
  function fromValue(value) {
    const input = clean(value).replace(/^arxiv\s*:\s*/i, "");
    const direct = paperId(input);
    if (direct) return direct;
    const href = safeUrl(input);
    if (!href) return null;
    return parse(
      {
        textContent: "",
        querySelector: () => null,
        querySelectorAll: (selector) =>
          selector === "a[href]" ? [{ getAttribute: () => href }] : [],
      },
      "https://arxiv.org/",
    ).id;
  }
  function searchUrl(citation) {
    return (
      "https://arxiv.org/search/?" +
      new URLSearchParams({
        query: citation.details?.title || citation.reference,
        searchtype: "all",
        abstracts: "show",
      })
    );
  }
  globalThis.LensReferenceParser = { parse, safeUrl, fromValue, searchUrl };
})();
