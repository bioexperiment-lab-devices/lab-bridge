document.querySelectorAll("pre > code").forEach((code) => {
  const pre = code.parentElement;
  const button = document.createElement("button");
  button.className = "copy-button";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(code.innerText);
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = "Copy"), 1200);
  });
  pre.appendChild(button);
});
