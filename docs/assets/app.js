(function () {
  const tabsRoot = document.querySelector("[data-tabs]");
  if (tabsRoot) {
    const tabs = Array.from(tabsRoot.querySelectorAll(".tab"));
    const panels = Array.from(document.querySelectorAll(".panel"));
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const id = tab.getAttribute("data-tab");
        tabs.forEach((item) => item.classList.toggle("active", item === tab));
        panels.forEach((panel) => {
          panel.classList.toggle("active", panel.getAttribute("data-panel") === id);
        });
      });
    });
  }

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const pre = button.previousElementSibling;
      if (!pre) return;
      const text = pre.innerText;
      try {
        await navigator.clipboard.writeText(text);
        const original = button.textContent;
        button.textContent = "已复制";
        setTimeout(() => {
          button.textContent = original;
        }, 900);
      } catch (err) {
        console.error(err);
      }
    });
  });

  const cfg = document.getElementById("cfg");
  const profile = document.getElementById("profile");
  const stage = document.getElementById("stage");
  const cores = document.getElementById("cores");
  const build = document.getElementById("build");
  const generated = document.getElementById("generated");

  if (build && generated) {
    build.addEventListener("click", () => {
      const cmd = [
        "./gmv run",
        `--config ${cfg.value.trim()}`,
        `--profile ${profile.value}`,
        `--stage ${stage.value}`,
        `--cores ${cores.value || 8}`,
        "--host hg38",
      ].join(" ");
      generated.innerHTML = `<code>${cmd}</code>`;
    });
  }
})();
