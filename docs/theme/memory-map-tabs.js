(() => {
    const root = document.querySelector(".memory-map");
    if (!root) return;

    const navigation = root.querySelector(".cpu-navigation");
    const viewport = root.querySelector(".cpu-viewport");
    const tabs = Array.from(root.querySelectorAll("[data-cpu-tab]"));
    const panels = Array.from(root.querySelectorAll("[data-cpu-panel]"));
    const steps = Array.from(root.querySelectorAll("[data-cpu-step]"));
    if (!navigation || !viewport || tabs.length === 0 || panels.length !== tabs.length) return;

    let selected = 0;
    const select = (index, { focus = false, updateHash = false } = {}) => {
        if (index < 0 || index >= tabs.length) return;
        selected = index;
        root.dataset.cpu = tabs[index].dataset.cpuTab;
        tabs.forEach((tab, position) => {
            tab.setAttribute("aria-selected", String(position === index));
            tab.tabIndex = position === index ? 0 : -1;
        });
        panels.forEach((panel, position) => {
            const active = position === index;
            panel.dataset.active = String(active);
            panel.style.setProperty("--panel-offset", position - index);
            panel.setAttribute("aria-hidden", String(!active));
            panel.inert = !active;
        });
        steps.forEach(button => {
            const next = index + Number(button.dataset.cpuStep);
            button.disabled = next < 0 || next >= tabs.length;
        });
        root.querySelector("[data-cpu-position]").textContent =
            `${root.dataset.cpu.toUpperCase()} · ${index + 1} / ${tabs.length}`;
        if (updateHash) {
            history.replaceState(null, "", `#${root.dataset.cpu}`);
            if (viewport.getBoundingClientRect().top < 0) {
                navigation.scrollIntoView({ block: "start" });
            }
        }
        if (focus) tabs[index].focus();
    };

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => select(index, { updateHash: true }));
        tab.addEventListener("keydown", event => {
            let next;
            if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
            if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
            if (event.key === "Home") next = 0;
            if (event.key === "End") next = tabs.length - 1;
            if (next === undefined) return;
            event.preventDefault();
            event.stopPropagation();
            select(next, { focus: true, updateHash: true });
        });
    });
    steps.forEach(button => {
        button.addEventListener("click", () => {
            select(selected + Number(button.dataset.cpuStep), { focus: true, updateHash: true });
        });
    });

    const selectFromHash = (initial = false) => {
        const target = document.getElementById(location.hash.slice(1));
        const cpu = target?.closest("[data-cpu-panel]")?.dataset.cpuPanel ?? location.hash.slice(1);
        const index = tabs.findIndex(tab => tab.dataset.cpuTab === cpu);
        if (index < 0 && !initial) return;
        select(index < 0 ? 0 : index);
    };
    selectFromHash(true);
    root.dataset.enhanced = "true";
    navigation.hidden = false;
    window.addEventListener("hashchange", () => selectFromHash());
})();
