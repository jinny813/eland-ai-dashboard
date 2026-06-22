import streamlit as st
import streamlit.components.v1 as components
import os

st.title("LocalStorage Test")

os.makedirs("comm_ui", exist_ok=True)
with open("comm_ui/index.html", "w") as f:
    f.write("""
    <script>
    function sendMessageToStreamlitClient(type, data) {
        window.parent.postMessage(Object.assign({isStreamlitMessage: true, type: type}, data), "*");
    }
    window.addEventListener("storage", function(e) {
        if (e.key === "AI_DIAGNOSE_REQ") {
            sendMessageToStreamlitClient("setComponentValue", {value: e.newValue});
        }
    });
    sendMessageToStreamlitClient("streamlit:componentReady", {apiVersion: 1});
    </script>
    """)

comm = components.declare_component("comm", path="comm_ui")
res = comm(key="comm")

st.components.v1.html("""
    <button onclick="localStorage.setItem('AI_DIAGNOSE_REQ', 'test_' + Math.random())">Send via LocalStorage</button>
""")

st.write("Received:", res)
