const form = document.querySelector('#salary-form');
const result = document.querySelector('#result');
const typeInput = document.querySelector('#player_type');
const apiBaseUrl = document.querySelector('.shell').dataset.apiUrl.replace(/\/$/, '');
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === tab));
  const type = tab.dataset.type; typeInput.value = type;
  document.querySelector('#batter-fields').classList.toggle('hidden', type !== 'batter');
  document.querySelector('#pitcher-fields').classList.toggle('hidden', type !== 'pitcher');
}));
form.addEventListener('submit', async event => {
  event.preventDefault();
  const type = typeInput.value;
  const group = document.querySelector(type === 'batter' ? '#batter-fields' : '#pitcher-fields');
  const stats = Object.fromEntries([...group.querySelectorAll('input')].map(x => [x.name, Number(x.value)]));
  result.textContent = '계산 중…';
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/predict`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({player_type: type, stats})});
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'API 오류');
    result.textContent = `제안 연봉: ${data.suggested_salary_krw.toLocaleString('ko-KR')}원 (${data.model_status})`;
  } catch (error) { result.textContent = `계산하지 못했습니다: ${error.message}. API 서버 설정을 확인하세요.`; }
});
