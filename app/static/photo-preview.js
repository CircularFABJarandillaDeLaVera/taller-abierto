document.querySelectorAll('[data-photo-input]').forEach(input => {
  const area = input.closest('fieldset').querySelector('[data-photo-preview]');
  let urls = [];
  input.addEventListener('change', () => {
    urls.forEach(url => URL.revokeObjectURL(url)); urls = []; area.replaceChildren();
    const files = [...input.files];
    if (files.length > 3) area.textContent = 'Selecciona como máximo tres fotografías.';
    files.forEach(file => {
      const item = document.createElement('div');
      const label = document.createElement('span'); label.textContent = `${file.name} (${(file.size / 1048576).toFixed(1)} MB)`; item.append(label);
      if (file.size > 5 * 1048576) item.append(' — supera 5 MB');
      else if (['image/jpeg', 'image/png'].includes(file.type)) {
        const url = URL.createObjectURL(file); urls.push(url);
        const img = document.createElement('img'); img.src = url; img.alt = `Vista previa de ${file.name}`; item.append(img);
      } else item.append(' — formato no admitido');
      area.append(item);
    });
  });
});
