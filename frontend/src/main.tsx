import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found in the document.");
}

ReactDOM.createRoot(rootElement).render(<App />);
