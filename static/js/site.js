(() => {
  const dialog = document.getElementById("search-dialog");
  const input = document.getElementById("search-input");
  const versionSelect = document.getElementById("search-version");
  const results = document.getElementById("search-results");
  const openButton = document.getElementById("search-open");
  const closeButton = document.getElementById("search-close");
  if (!dialog || !input || !versionSelect || !results) return;
  let pagesPromise;
  const searchURL = new URL("index.json", document.querySelector(".brand").href);

  function openSearch() {
    dialog.showModal();
    input.focus();
    if (!pagesPromise) {
      pagesPromise = fetch(searchURL).then(response => {
        if (!response.ok) throw new Error("Search index unavailable");
        return response.json();
      });
    }
    renderResults();
  }

  async function renderResults() {
    const query = input.value.trim().toLocaleLowerCase();
    const selectedVersion = versionSelect.value;
    if (!query) {
      results.textContent = document.documentElement.dataset.searchEmpty;
      return;
    }
    try {
      const pages = await pagesPromise;
      if (query !== input.value.trim().toLocaleLowerCase() || selectedVersion !== versionSelect.value) return;
      const matches = pages.filter(page =>
        (selectedVersion === "all" || page.version === selectedVersion) &&
        (page.title + " " + page.summary).toLocaleLowerCase().includes(query)
      ).slice(0, 30);
      results.replaceChildren();
      if (!matches.length) {
        results.textContent = document.documentElement.dataset.searchNoResults;
        return;
      }
      for (const page of matches) {
        const link = document.createElement("a");
        link.className = "search-result";
        link.href = page.url;
        const title = document.createElement("strong");
        title.textContent = page.title;
        const heading = document.createElement("div");
        heading.className = "search-result-heading";
        heading.append(title);
        if (page.version) {
          const version = document.createElement("span");
          version.className = "search-result-version";
          version.textContent = `PostgreSQL ${page.version}`;
          heading.append(version);
        }
        const summary = document.createElement("span");
        summary.textContent = page.summary;
        link.append(heading, summary);
        results.append(link);
      }
    } catch {
      results.textContent = document.documentElement.dataset.searchError;
    }
  }

  openButton.addEventListener("click", openSearch);
  closeButton.addEventListener("click", () => dialog.close());
  input.addEventListener("input", renderResults);
  versionSelect.addEventListener("change", renderResults);
  dialog.addEventListener("click", event => {
    if (event.target === dialog) dialog.close();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      openSearch();
    }
  });
})();

(() => {
  const menus = ["header-version-menu", "header-language-menu"]
    .map(id => document.getElementById(id)).filter(Boolean);
  if (!menus.length) return;
  for (const menu of menus) {
    menu.addEventListener("toggle", () => {
      if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; });
    });
  }
  document.addEventListener("click", event => {
    menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      menus.forEach(menu => {
        if (menu.open) {
          menu.open = false;
          menu.querySelector("summary").focus();
        }
      });
    }
  });
})();

(() => {
  const sidebar = document.getElementById("manual-sidebar");
  if (!sidebar) return;

  const tree = sidebar.querySelector(".manual-tree");
  let navigationPromise;

  function createNode(node, path, depth) {
    const wrapper = document.createElement("div");
    wrapper.className = `manual-nav-node depth-${depth}`;
    const row = document.createElement("div");
    row.className = "manual-nav-row";
    if (node.children.length) {
      const toggle = document.createElement("button");
      toggle.className = "manual-nav-toggle";
      toggle.type = "button";
      toggle.setAttribute("aria-controls", `nav-lazy-${path}`);
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", `${document.documentElement.dataset.expandOrCollapse} ${node.title}`);
      const arrow = document.createElement("span");
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "›";
      toggle.append(arrow);
      row.append(toggle);
    } else {
      const spacer = document.createElement("span");
      spacer.className = "manual-nav-spacer";
      spacer.setAttribute("aria-hidden", "true");
      row.append(spacer);
    }
    const link = document.createElement("a");
    link.className = "manual-nav-link";
    link.href = new URL(node.href, new URL(tree.dataset.manualBase, location.origin)).href;
    link.textContent = node.title;
    row.append(link);
    wrapper.append(row);
    if (node.children.length) {
      const children = document.createElement("div");
      children.className = "manual-nav-children";
      children.id = `nav-lazy-${path}`;
      children.dataset.navPath = path;
      children.hidden = true;
      wrapper.append(children);
    }
    return wrapper;
  }

  if (tree) tree.addEventListener("click", async event => {
    const toggle = event.target.closest(".manual-nav-toggle");
    if (!toggle || !tree.contains(toggle)) return;
    const children = document.getElementById(toggle.getAttribute("aria-controls"));
    if (!children) return;
    if (!children.dataset.loaded) {
      toggle.disabled = true;
      try {
        if (!navigationPromise) {
          navigationPromise = fetch(tree.dataset.navUrl).then(response => {
            if (!response.ok) throw new Error("Navigation unavailable");
            return response.json();
          });
        }
        const navigation = await navigationPromise;
        const path = children.dataset.navPath.split("-").map(Number);
        let nodes = navigation.sections;
        let node;
        for (const index of path) {
          node = nodes[index];
          if (!node) throw new Error("Navigation entry unavailable");
          nodes = node.children;
        }
        nodes.forEach((child, index) => children.append(createNode(child, `${children.dataset.navPath}-${index}`, path.length)));
        children.dataset.loaded = "true";
      } catch {
        navigationPromise = null;
        toggle.title = document.documentElement.dataset.navigationError;
        return;
      } finally {
        toggle.disabled = false;
      }
    }
    children.hidden = !children.hidden;
    toggle.setAttribute("aria-expanded", String(!children.hidden));
  });

  const active = sidebar.querySelector(".manual-nav-link.is-current, .manual-nav-home.is-current");
  if (active) {
    requestAnimationFrame(() => {
      sidebar.scrollTop = Math.max(0, active.offsetTop - sidebar.offsetTop - sidebar.clientHeight / 3);
    });
  }

  const open = document.getElementById("manual-nav-open");
  const close = document.getElementById("manual-nav-close");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (!open || !close || !backdrop) return;

  function setOpen(value) {
    sidebar.classList.toggle("is-open", value);
    backdrop.hidden = !value;
    document.body.classList.toggle("nav-open", value);
    open.setAttribute("aria-expanded", String(value));
    if (value) close.focus();
    else open.focus();
  }
  open.addEventListener("click", () => setOpen(true));
  close.addEventListener("click", () => setOpen(false));
  backdrop.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && sidebar.classList.contains("is-open")) setOpen(false);
  });
})();
