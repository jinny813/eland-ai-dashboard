import streamlit as st
import streamlit.components.v1 as components
import os

st.title("Component Test")

_test_comp = components.declare_component("test_comp", path="test_ui")

if not os.path.exists("test_ui"):
    os.makedirs("test_ui")

with open("test_ui/index.html", "w") as f:
    f.write("""
    <html><body>
    <div id="output">Waiting...</div>
    <script>
    function sendMessageToStreamlitClient(type, data) {
        var outData = Object.assign({isStreamlitMessage: true, type: type}, data);
        window.parent.postMessage(outData, "*");
    }
    function sendValue() {
        sendMessageToStreamlitClient("setComponentValue", {value: "Hello from JS!"});
    }
    window.addEventListener("message", function(e) {
        if (e.data.type === "streamlit:render") {
            const args = e.data.args;
            document.getElementById("output").innerText = "Received from Python: " + JSON.stringify(args);
        }
    });
    sendMessageToStreamlitClient("streamlit:componentReady", {apiVersion: 1});
    sendMessageToStreamlitClient("streamlit:setFrameHeight", {height: 200});
    </script>
    <button onclick="sendValue()">Click Me</button>
    </body></html>
    """)

# Create session state for report
if "report" not in st.session_state:
    st.session_state.report = None

val = _test_comp(key="my_test", report=st.session_state.report)
st.write("Value from JS:", val)

if val == "Hello from JS!" and st.session_state.report is None:
    # Simulate AI process
    st.session_state.report = "AI DIAGNOSIS RESULT!"
    st.rerun()
