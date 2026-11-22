const forms = document.querySelectorAll('form[data-run-form]');
const printButton = document.querySelector('#print');

printButton?.addEventListener('click', () => window.print());

forms.forEach((form) => {
  const feedback = form.querySelector('output');
  const submit = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    delete feedback.dataset.error;
    feedback.value = '正在结算…';
    submit.disabled = true;
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form)});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || '结算失败，请重试。');
      window.location.assign(payload.location);
    } catch (error) {
      feedback.dataset.error = '';
      feedback.value = error.message || '请求失败，请重试。';
      submit.disabled = false;
    }
  });
});
