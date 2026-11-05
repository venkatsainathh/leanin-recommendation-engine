/* Read-only member experience; all recommendations come from the existing API. */
const $ = (id) => document.getElementById(id);
const formats = {virtual: 'Virtual', hybrid: 'Hybrid', in_person: 'In person'};
const palettes = [['#eee2f1','#80538c'],['#f5dfcb','#ae6a39'],['#e4e9db','#677548'],['#e0e9ee','#527381']];
let members = [], recommendations = [], activeFormat = 'all', visible = 6, requestNumber = 0;
// All source strings enter the DOM through textContent; never interpolate data as HTML.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function modal(title, nodes) {
  $('dialog-content').replaceChildren(element('p','eyebrow','A LITTLE MORE ABOUT YOUR CIRCLE'));
  const heading = element('h2','',title); heading.id = 'dialog-title';
  $('dialog-content').append(heading,...nodes);
  $('detail').showModal();
}
function showHow() {
  modal('A community that fits your next chapter.', [
    element('p','','We look for Circles that share your interests and have room for new members. Recent activity helps us find communities where conversations are happening.'),
    element('p','','We mix topics so you can explore different kinds of support. If you’re new or haven’t added interests, we suggest active communities to help you get started.'),
    element('p','notice','This is a demonstration using synthetic members and a dated activity snapshot. You can explore recommendations, but joining and messaging are not available.')
  ]);
}
function details(circle) {
  const list = element('dl');
  const fields = [ ['Meeting format',formats[circle.format]], ['Meeting location',circle.location || (circle.format === 'virtual' ? 'Online · meeting link not provided' : 'Not provided · confirm with the organizer')], ['Community size',`${circle.member_count} members`], ['Availability',circle.available_seats === null ? 'No membership cap is set' : `${circle.available_seats} places available in this snapshot`], ['How joining works',circle.join_policy === 'open' ? 'Open to new members' : 'Request required · approval is not guaranteed'] ];
  fields.forEach(([label,value])=>list.append(element('dt','',label),element('dd','',value)));
  modal(circle.name,[element('p','',circle.description || 'Explore a community for shared learning and support.'),element('p','reason',circle.explanation),list,element('p','',`Topics: ${circle.topics.join(', ') || 'No topics listed'}`),element('p','notice','Interested? In a full product, you could contact the organizer or join here. This take-home demo does not submit membership requests.')]);
}
function card(circle,index) {
  const node = element('article','card');
  const [wash,accent] = palettes[index % palettes.length];
  node.style.setProperty('--wash',wash); node.style.setProperty('--accent',accent);
  const art = element('div','card-art');
  const symbol = element('span','card-symbol',['✳','◒','✺','◎'][index%4]); symbol.setAttribute('aria-hidden','true');
  art.append(element('span','format-badge',formats[circle.format]),symbol);
  const body = element('div','card-body');
  const reason = element('div','reason');
  reason.append(element('strong','','WHY THIS COULD BE YOUR CIRCLE'),element('span','',circle.explanation));
  const facts=element('div','facts');
  facts.append(element('span','',`${circle.member_count} members`),element('span','seat',circle.available_seats === null ? 'Welcoming new members' : `${circle.available_seats} places available`));
  const bottom=element('div','card-bottom'), button=element('button','view-button','Explore Circle ↗');
  button.setAttribute('aria-label',`Explore ${circle.name}`);button.addEventListener('click',()=>details(circle));
  bottom.append(element('span','join-status',circle.join_policy === 'open' ? 'Open to join' : 'Request to join'),button);
  body.append(element('h3','',circle.name),element('p','description',circle.description || 'A space for connection, shared experiences, and growth.'),reason,facts,bottom);
  node.append(art,body);return node;
}
function render() {
  if (!$('member').value) {
    $('cards').replaceChildren();
    $('cards').setAttribute('aria-busy', 'false');
    $('count').textContent = '';
    $('more').hidden = true;
    $('message').replaceChildren(element('div', 'empty', 'Select or search for a member above to see their recommended Circles.'));
    return;
  }
  const filtered=recommendations.filter(c=>activeFormat==='all'||c.format===activeFormat);
  $('cards').replaceChildren(...filtered.slice(0,visible).map(card));
  $('message').replaceChildren();
  if (!filtered.length) $('message').append(element('div','empty',activeFormat === 'all' ? 'No Circles are available for this member right now. Try another demo member.' : 'No recommendations in this format. Try All formats to explore other communities.'));
  $('count').textContent=`${filtered.length} ${filtered.length === 1 ? 'Circle' : 'Circles'} for you`;
  $('more').hidden=filtered.length<=visible;
}
async function load() {
  const current=++requestNumber;
  const member=members.find(m=>m.id===Number($('member').value));
  if (!member) { render(); return; }
  visible=6;recommendations=[];
  $('greeting').textContent=`Find your people, ${member.first_name}.`;
  $('context').textContent=member.interests.length ? 'Inspired by your interests. Chosen to help you connect and grow.' : 'New beginnings, shared ambitions. Explore active communities to get started.';
  $('interests').replaceChildren(...member.interests.map(t=>element('span','interest',t)));
  $('cards').replaceChildren();$('cards').setAttribute('aria-busy','true');$('more').hidden=true;$('count').textContent='';
  $('message').replaceChildren(element('div','loading','Finding your next community…'));
  try {
    const response=await fetch(`/recommendations/${member.id}?limit=50`);
    if(!response.ok) throw new Error('Recommendations could not be loaded.');
    const data=await response.json();
    if(current!==requestNumber)return;
    recommendations=data.recommendations;
    const date=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(data.metadata.as_of));
    $('snapshot').textContent=`Demo data · ${data.metadata.clock_mode === 'snapshot' ? 'Snapshot' : 'Evaluated'} ${date}. Joining is not enabled.`;
    render();
  } catch {
    if(current!==requestNumber)return;
    const box=element('div','error','We couldn’t load your Circles. Check that the local server is running. ');
    const retry=element('button','text-button','Try again');retry.addEventListener('click',load);box.append(retry);$('message').replaceChildren(box);
  } finally {if(current===requestNumber)$('cards').setAttribute('aria-busy','false');}
}
$('more').addEventListener('click',()=>{visible+=6;render();});
document.querySelectorAll('[data-format]').forEach(button=>button.addEventListener('click',()=>{
  activeFormat=button.dataset.format;visible=6;
  document.querySelectorAll('[data-format]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});render();
}));
$('why').addEventListener('click',showHow);$('about').addEventListener('click',showHow);
$('detail').querySelector('.close').addEventListener('click',()=>$('detail').close());
function initializeMemberSearch() {
  const input = $('member-search');
  const list = $('member-options');
  const picker = $('member-picker');
  let matches = [], active = -1;
  const name = member => `${member.first_name} ${member.last_name}`;
  const selected = () => members.find(member => String(member.id) === $('member').value);
  function close() {
    list.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    input.value = selected() ? name(selected()) : '';
    $('member-search-status').textContent = '';
    active = -1;
  }
  function choose(member) {
    const changed = $('member').value !== String(member.id);
    $('member').value = member.id;
    close();
    if (changed) load();
  }
  function highlight(index) {
    active = index;
    Array.from(list.children).forEach((option, i) => option.classList.toggle('highlighted', i === active));
    if (active >= 0) {
      const option = list.children[active];
      input.setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({block: 'nearest'});
    } else input.removeAttribute('aria-activedescendant');
  }
  function open(query = '') {
    const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    matches = members.filter(member => {
      const searchable = `${name(member)} ${member.id} ${member.interests.join(' ')}`.toLocaleLowerCase();
      return words.every(word => searchable.includes(word));
    });
    list.replaceChildren(...matches.map(member => {
      const option = element('li', 'member-option');
      option.id = `member-option-${member.id}`;
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', String(String(member.id) === $('member').value));
      option.append(element('span', 'member-option-name', name(member)),
        element('span', 'member-option-info', `Member ${member.id} · ${member.interests.join(', ') || 'No interests added yet'}`));
      option.addEventListener('mousedown', event => event.preventDefault());
      option.addEventListener('click', () => choose(member));
      return option;
    }));
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    highlight(-1);
    $('member-search-status').textContent = matches.length ? `${matches.length} members found. Use arrow keys to select.` : 'No members found. Try another name or interest.';
  }
  input.disabled = false;
  input.value = selected() ? name(selected()) : '';
  input.addEventListener('focus', () => { input.select(); open(); });
  input.addEventListener('click', () => { if (list.hidden) { input.select(); open(); } });
  input.addEventListener('input', () => open(input.value));
  input.addEventListener('keydown', event => {
    if (event.isComposing) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (list.hidden) open();
      if (matches.length) highlight(active < 0 ? (event.key === 'ArrowDown' ? 0 : matches.length - 1) :
        (active + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length);
    } else if (event.key === 'Enter' && !list.hidden) {
      event.preventDefault();
      if (active >= 0) choose(matches[active]);
      else if (matches.length === 1) choose(matches[0]);
    } else if (event.key === 'Escape') { event.preventDefault(); close(); }
    else if (event.key === 'Tab') close();
  });
  picker.addEventListener('focusout', event => { if (!picker.contains(event.relatedTarget)) close(); });
  document.addEventListener('click', event => { if (!picker.contains(event.target)) close(); });
}

async function init(){
  try{
    const response=await fetch('/demo/members');if(!response.ok)throw new Error('Unable to load members');
    members=await response.json();
    members.sort((a, b) => a.id - b.id);
    if (!members.length) throw new Error('No demo members available');
    $('member').value = '';
    initializeMemberSearch();
    render();
  }catch(error){console.error('Member search initialization failed:', error);$('member-search').placeholder = 'Members unavailable';$('message').replaceChildren(element('div','error','The demo could not load. Refresh this page after starting the local server.'));$('cards').setAttribute('aria-busy','false');}
}
init();
