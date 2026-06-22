import streamlit as st
import streamlit.components.v1 as components
import os

st.title("postMessage Broadcast Test")

os.makedirs("comm_ui2", exist_ok=True)
with open("comm_ui2/index.html", "w") as f:
    f.write("""
    <html><body>
    <div>Bridge Component</div>
    <script>
    function sendMessageToStreamlitClient(type, data) {
        window.parent.postMessage(Object.assign({isStreamlitMessage: true, type: type}, data), "*");
    }
    window.addEventListener("message", function(e) {
        if (e.data.type === "AI_REQ") {
            sendMessageToStreamlitClient("setComponentValue", {value: e.data.payload});
            
            // simulate python response after 1s
            setTimeout(() => {
                for (let i=0; i<window.parent.frames.length; i++) {
                    window.parent.frames[i].postMessage({type: "AI_RES", payload: "SUCCESS!"}, "*");
                }
            }, 1000);
        }
    });
    sendMessageToStreamlitClient("streamlit:componentReady", {apiVersion: 1});
    </script>
    </body></html>
    """)

comm = components.declare_component("comm2", path="comm_ui2")
res = comm(key="comm2")

st.components.v1.html("""
    <html><body>
    <button onclick="sendReq()">Send via postMessage</button>
    <div id="out"></div>
    <script>
    function sendReq() {
        for (let i=0; i<window.parent.frames.length; i++) {
            window.parent.frames[i].postMessage({type: "AI_REQ", payload: "test_payload"}, "*");
        }
    }
    window.addEventListener("message", function(e) {
        if (e.data.type === "AI_RES") {
            document.getElementById("out").innerText = e.data.payload;
        }
    });
    </script>
    </body></html>
""", height=200)

st.write("Python Received:", res)
