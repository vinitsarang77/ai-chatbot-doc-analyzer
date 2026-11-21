document.getElementById("askForm").onsubmit = async (e) => {
    e.preventDefault();
    let input = document.getElementById("questionInput");
    let userText = input.value.trim();
    if (!userText) return;

    let chatBox = document.getElementById("chat-box");
    let loading = document.getElementById("ans-loading");

    // 1. Append user message bubble
    let userBubble = document.createElement("div");
    userBubble.className = "chat-msg user-msg";
    userBubble.innerText = userText;
    chatBox.appendChild(userBubble);
    chatBox.scrollTop = chatBox.scrollHeight;

    let formData = new FormData(e.target);
    input.value = ""; // clear input box
    loading.style.display = "block";

    // 2. Fetch AI reply
    let res = await fetch("/ask", {
        method: "POST",
        body: formData
    });
    let data = await res.json();
    loading.style.display = "none";

    // 3. Append AI message bubble
    let botBubble = document.createElement("div");
    botBubble.className = "chat-msg bot-msg";
    botBubble.innerHTML = marked.parse(data.response);
    chatBox.appendChild(botBubble);
    chatBox.scrollTop = chatBox.scrollHeight;
};

document.getElementById("clearChatBtn").onclick = async () => {
    await fetch("/clear_chat", { method: "POST" });
    document.getElementById("chat-box").innerHTML = "";
};

document.getElementById("emailForm").onsubmit = async (e) => {
    e.preventDefault();
    let formData = new FormData(e.target);

    let loading = document.getElementById("summary-loading");
    loading.style.display = "block";

    let res = await fetch("/summarize", {
        method: "POST",
        body: formData
    });

    let data = await res.json();
    document.getElementById("summary").innerHTML = marked.parse(data.response);

    loading.style.display = "none"; // hide loader
};

document.getElementById("extractForm").onsubmit = async (e) => {
    e.preventDefault();
    let formData = new FormData(e.target);

    let loading = document.getElementById("extract-loading");
    let analysisBox = document.getElementById("extract-analysis");
    let rawDetails = document.getElementById("raw-data-details");
    let rawBox = document.getElementById("extracted-raw");

    loading.style.display = "block";
    analysisBox.style.display = "none";
    rawDetails.style.display = "none";

    let res = await fetch("/extract", {
        method: "POST",
        body: formData
    });

    let data = await res.json();
    loading.style.display = "none";

    if (data.response) {
        analysisBox.innerHTML = marked.parse(data.response);
        analysisBox.style.display = "block";
    } else {
        analysisBox.innerHTML = marked.parse(data.analysis);
        analysisBox.style.display = "block";
        rawBox.innerText = data.extracted_text;
        rawDetails.style.display = "block";
    }
};