const form = document.querySelector('#salary-form');
const result = document.querySelector('#result');
const typeInput = document.querySelector('#player_type');
const apiBaseUrl = (document.querySelector('.shell').dataset.apiUrl || 'http://127.0.0.1:8001').replace(/\/$/, '');
const submit = form.querySelector('.submit');
let pending = false;
function selectType(type) {
  typeInput.value = type;
  const label = type === 'batter' ? '타자' : '투수';
  document.querySelectorAll('.tab').forEach(tab => {
    const selected = tab.dataset.type === type;
    tab.classList.toggle('active', selected);
    tab.setAttribute('aria-pressed', String(selected));
  });
  ['batter', 'pitcher'].forEach(name => {
    const group = document.querySelector('#' + name + '-fields');
    const inactive = name !== type;
    group.hidden = inactive;
    group.classList.toggle('hidden', inactive);
    group.querySelectorAll('input').forEach(input => { input.disabled = inactive; input.required = !inactive; });
  });
  document.querySelector('#selected-type').textContent = '선택한 유형: ' + label + ' · ' + (type === 'batter' ? '타격' : '투구') + ' 성적 입력';
  submit.textContent = label + ' 제안 연봉 계산하기';
  result.textContent = label + ' 성적을 입력해 계산해 보세요.';
}
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => { if (!pending) selectType(tab.dataset.type); }));
selectType(typeInput.value);
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (pending || !form.reportValidity()) return;
  const type = typeInput.value;
  const label = type === 'batter' ? '타자' : '투수';
  const group = document.querySelector('#' + type + '-fields');
  const stats = Object.fromEntries([...group.querySelectorAll('input')].map(x => [x.name, Number(x.value)]));
  pending = true; submit.disabled = true;
  document.querySelectorAll('.tab').forEach(tab => { tab.disabled = true; });
  result.textContent = label + ' 연봉 계산 중…';
  try {
    const response = await fetch(apiBaseUrl + '/api/v1/predict', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({player_type: type, stats}), signal: AbortSignal.timeout(15000)
    });
    if (!response.ok) throw new Error('API 응답 오류 (HTTP ' + response.status + ')');
    const data = await response.json();
    if (!Number.isInteger(data.suggested_salary_krw) || data.suggested_salary_krw <= 0) throw new Error('유효한 연봉을 받지 못했습니다');
    result.textContent = label + ' 제안 연봉: ' + data.suggested_salary_krw.toLocaleString('ko-KR') + '원 (' + data.model_status + ')';
  } catch (error) {
    result.textContent = '계산 실패: ' + error.message + '. API 서버(8001) 실행 및 API 주소 설정을 확인하세요.';
  } finally {
    pending = false; submit.disabled = false;
    document.querySelectorAll('.tab').forEach(tab => { tab.disabled = false; });
  }
});
