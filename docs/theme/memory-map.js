(() => {
    const root = document.querySelector(".memory-map");
    if (!root) return;

    const state = { view: "compare", topic: "overview" };
    const update = () => {
        root.dataset.view = state.view;
        for (const button of root.querySelectorAll("button[data-control]")) {
            button.setAttribute("aria-pressed", String(state[button.dataset.control] === button.dataset.value));
        }
        for (const section of root.querySelectorAll("[data-topic]")) {
            section.hidden = state.topic !== "overview" && section.dataset.topic !== state.topic;
        }
        for (const panel of root.querySelectorAll("[data-era]")) {
            panel.hidden = state.view !== "compare" && panel.dataset.era !== state.view;
        }
        root.querySelector("[data-status]").textContent =
            `${state.view === "compare" ? "Current and proposed future" : state.view === "current" ? "Current implementation" : "Proposed future"} · ${state.topic === "overview" ? "All memory regions" : state.topic === "flash" ? "Flash & SD" : state.topic.toUpperCase()}`;
    };

    for (const button of root.querySelectorAll("button[data-control]")) {
        button.addEventListener("click", () => {
            state[button.dataset.control] = button.dataset.value;
            update();
        });
    }
    update();
    root.querySelector(".map-controls").hidden = false;
})();
