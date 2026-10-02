import { useEffect } from 'react';
import { boot } from './boot.js';

export default function App() {
  useEffect(() => {
    boot();
  }, []);

  return (
    <>
      <div className="mobile-bar">
        <button id="mMenu" aria-label="Menu" />
        <div className="wordmark">
          <b>FOCUSED</b>LEARNING
        </div>
        <button className="add-m" id="mAdd" aria-label="Add document" />
      </div>

      <div id="app">
        <aside id="sidebar" />
        <main id="main" />
      </div>

      <div id="dropover">
        <div className="frame">
          <div className="in">
            <div className="big">Drop to capture</div>
            <div className="small">PDF · DOCX · PPTX · IMAGES (OCR) · MD · TXT · HTML · RTF — parsed locally, never uploaded</div>
          </div>
        </div>
      </div>
      <div id="toasts" />
      <input
        type="file"
        id="fileInput"
        multiple
        hidden
        accept=".pdf,.docx,.doc,.txt,.md,.markdown,.html,.htm,.rtf,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.webp,.svg,image/*"
      />
      <input type="file" id="importInput" hidden accept=".json" />
    </>
  );
}
