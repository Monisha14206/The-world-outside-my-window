import React, { useEffect, useState } from 'react'
import { Leaf, Feather, ArrowUp, ArrowDown, X, Sparkles, Trash2, Heart, Printer, Search, Footprints } from 'lucide-react'

const ACT = ['Walk','Nature','Friends','Café','City Exploration','Travel','Event','Other']
const MOODS = ['Happy','Peaceful','Excited','Curious','Nostalgic','Tired','Sad','Lonely','Mixed feelings','Other']
const PROMPTS = ['Take a different route home today.','Find a place nearby to watch the sunset.','Spend ten minutes noticing the little things around you.','Visit a local park you have never explored.','Take a walk without listening to anything.','Notice a tree, flower, or bird you normally overlook.','Meet a friend without planning every minute.']
const today = () => new Date().toISOString().slice(0, 10)
const blank = () => ({ date: today(), title: '', places: '', activity: 'Walk', people: '', notes: '', emotions: [], reflection: '', story: '', feelings: '', details: [], favorite: false, photos: [] })
const api = async (url, opts) => { const r = await fetch(url, opts); const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.error || 'Something went wrong'); return j }
const src = p => p.url || '/uploads/' + p.file

export default function App() {
  const [view, setView] = useState('home'), [list, setList] = useState([]), [cur, setCur] = useState(null), [status, setStatus] = useState(null), [loadErr, setLoadErr] = useState('')
  const load = () => api('/api/journals').then(l => { setList(l); setLoadErr('') }).catch(() => setLoadErr("Can't reach the journal backend. Start it with: python app.py (see README)."))
  useEffect(() => { load(); api('/api/health').then(setStatus).catch(() => setStatus({ ollama: false, hint: 'Backend is not running. Start it with: python app.py' })) }, [])
  const go = (v, e) => { setCur(e || null); setView(v); window.scrollTo(0, 0) }
  const write = seed => go('write', { ...blank(), ...seed })
  return <>
    <nav aria-label="Main"><span className="brand"><Leaf size={20}/>The World Outside My Window</span>
      {[['home','Home'],['library','My Journal'],['explore','Explore']].map(([k, l]) => <a key={k} className={view === k ? 'on' : ''} tabIndex={0} onKeyDown={e => e.key === 'Enter' && go(k)} onClick={() => go(k)}>{l}</a>)}
      <button className="pri" onClick={() => write()}><Feather size={16}/>Write today's story</button></nav>
    <main>
      {view === 'home' && <Home write={() => write()} lib={() => go('library')} status={status}/>}
      {view === 'write' && <Editor key={cur?.id || 'new'} init={cur} status={status} done={e => { load(); go('entry', e) }}/>}
      {view === 'library' && <Library err={loadErr} list={list} open={e => go('entry', e)} write={() => write()}/>}
      {view === 'entry' && cur && <Entry e={cur} edit={() => go('write', cur)} gone={() => { load(); go('library') }} reload={x => setCur(x)} refresh={load}/>}
      {view === 'explore' && <Explore start={p => write({ title: '', notes: 'Today\'s outdoor prompt: ' + p + '\n\n' })}/>}
    </main></>
}

function Home({ write, lib, status }) {
  return <>
    <section className="hero"><div>
      <p className="hand">a collection of days lived, not just days passed</p>
      <h1>The World Outside My Window</h1>
      <h2 style={{ fontStyle: 'italic' }}>Some days become memories before we even realize it.</h2>
      <p>Collect the places you wander, the people you meet, the little things you notice, and the feelings you bring home.</p>
      <div className="bar"><button className="pri" onClick={write}>Start my journal</button><button onClick={lib}>Explore my memories</button></div></div>
      <img alt="A person walking in a green landscape" src="https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=800&q=70" onError={e => e.target.style.visibility = 'hidden'}/></section>
    <div className="band"><h2>The little things matter</h2><p>Memories aren't only holidays. A different route home, a café you stumbled into, a quiet hour in a park — they all belong here.</p></div>
    <h2>Three simple steps</h2><div className="row">{['Step outside and live your day.','Add your photos and tell your story.','Let a local open-weight AI help you shape it.'].map((t, i) => <p key={i}><b>{i + 1}.</b> {t}</p>)}</div>
    <div className="band"><h2>Open-source AI with a purpose</h2><p>Stories are written by an open-weight model running on your own computer through Ollama. Nothing is sent to a hosted AI service. This is a local single-user prototype.</p>
      <p><b>AI status:</b> {!status ? 'checking…' : status.ollama && status.modelInstalled ? `ready (${status.model})` : status.hint}</p></div>
    <footer className="hand">Made for the Hacktoberfest Open-Source AI Challenge — Week 1: Touch Grass. Go outside. Keep the memories in here.</footer></>
}

function Editor({ init, status, done }) {
  const [f, setF] = useState(init), [files, setFiles] = useState({}), [busy, setBusy] = useState(''), [err, setErr] = useState(''), [orig, setOrig] = useState(init.notes)
  const set = (k, v) => setF(p => ({ ...p, [k]: v }))
  const addPhotos = e => {
    setErr(''); const add = []
    for (const file of e.target.files) {
      if (!/\.(jpe?g|png|webp)$/i.test(file.name)) { setErr(`'${file.name}' isn't a JPG, PNG or WebP image.`); continue }
      if (file.size > 8 * 1024 * 1024) { setErr(`'${file.name}' is over 8 MB.`); continue }
      const id = crypto.randomUUID(); setFiles(x => ({ ...x, [id]: file })); add.push({ new: true, id, url: URL.createObjectURL(file), caption: '' })
    }
    setF(p => ({ ...p, photos: [...p.photos, ...add] })); e.target.value = ''
  }
  const move = (i, d) => setF(p => { const a = [...p.photos]; const j = i + d; if (j < 0 || j >= a.length) return p; [a[i], a[j]] = [a[j], a[i]]; return { ...p, photos: a } })
  const cap = (i, v) => setF(p => ({ ...p, photos: p.photos.map((x, k) => k === i ? { ...x, caption: v } : x) }))
  const payload = () => ({ ...f, captions: f.photos.map(p => p.caption), notes: f.notes + (f.reflection ? '\n\nReflection: ' + f.reflection : '') })
  const ai = async (task) => {
    setBusy(task); setErr('')
    try {
      const r = await api('/api/ai/' + (task === 'journal' ? 'generate-journal' : task === 'title' ? 'generate-title' : 'generate-captions'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload()) })
      setF(p => ({ ...p, ...(r.title ? { title: r.title } : {}), ...(r.story ? { story: r.story, feelings: r.feelings || '', details: r.details || [] } : {}),
        photos: r.captions?.length ? p.photos.map((x, i) => ({ ...x, caption: r.captions[i] || x.caption })) : p.photos }))
    } catch (e) { setErr(e.message) } finally { setBusy('') }
  }
  const save = async () => {
    setErr(''); setBusy('save')
    const fd = new FormData(); const data = { ...f, photos: f.photos.map(p => p.new ? { new: true, caption: p.caption } : { file: p.file, caption: p.caption }) }
    delete data.id; f.photos.filter(p => p.new).forEach(p => fd.append('photos', files[p.id])); fd.append('data', JSON.stringify(data))
    try { done(await api(f.id ? '/api/journals/' + f.id : '/api/journals', { method: f.id ? 'PUT' : 'POST', body: fd })) } catch (e) { setErr(e.message); setBusy('') }
  }
  const ready = status?.ollama && status?.modelInstalled
  return <section><h2>{f.id ? 'Edit this memory' : 'A blank page for today'}</h2>
    {err && <div className="err" role="alert">{err}</div>}
    <div className="row"><div><label htmlFor="d">Date</label><input id="d" type="date" value={f.date} onChange={e => set('date', e.target.value)}/></div>
      <div><label htmlFor="p">Place(s) visited</label><input id="p" value={f.places} onChange={e => set('places', e.target.value)}/></div>
      <div><label htmlFor="a">Activity</label><select id="a" value={f.activity} onChange={e => set('activity', e.target.value)}>{ACT.map(a => <option key={a}>{a}</option>)}</select></div>
      <div><label htmlFor="w">With (optional)</label><input id="w" value={f.people} onChange={e => set('people', e.target.value)}/></div></div>
    <label htmlFor="t">Title (optional)</label><input id="t" value={f.title} onChange={e => set('title', e.target.value)}/>
    <label htmlFor="ph">Photo memories (JPG, PNG, WebP — up to 8 MB each)</label><input id="ph" type="file" multiple accept=".jpg,.jpeg,.png,.webp" onChange={addPhotos}/>
    <div className="polaroids">{f.photos.map((p, i) => <div className="pol" key={p.id || p.file}><img src={src(p)} alt={p.caption || 'Your photo'}/>
      <input aria-label="Photo caption" placeholder="a few words…" value={p.caption} onChange={e => cap(i, e.target.value)}/>
      <div className="ctl"><button aria-label="Move earlier" onClick={() => move(i, -1)}><ArrowUp size={14}/></button><button aria-label="Move later" onClick={() => move(i, 1)}><ArrowDown size={14}/></button>
        <button aria-label="Remove photo" onClick={() => setF(q => ({ ...q, photos: q.photos.filter((_, k) => k !== i) }))}><X size={14}/></button></div></div>)}</div>
    <label htmlFor="n">Tell me about your day</label>
    <textarea id="n" value={f.notes} onChange={e => set('notes', e.target.value)} placeholder="Tell me about your day... Where did you go? What happened? Who did you meet? What made you smile? Was there a moment you want to remember forever?"/>
    <label>How did it feel? (choose any)</label><div className="chips">{MOODS.map(m => <button key={m} className={'chip' + (f.emotions.includes(m) ? ' on' : '')} aria-pressed={f.emotions.includes(m)} onClick={() => set('emotions', f.emotions.includes(m) ? f.emotions.filter(x => x !== m) : [...f.emotions, m])}>{m}</button>)}</div>
    <label htmlFor="r">Personal reflection — favourite moment, a little detail, something you're grateful for (optional)</label><textarea id="r" style={{ minHeight: 90, fontSize: '1.05rem' }} value={f.reflection} onChange={e => set('reflection', e.target.value)}/>
    {!ready && <div className="err">AI is unavailable. {status?.hint} You can still save your own words.</div>}
    <div className="bar"><button className="pri" disabled={!ready || !!busy} onClick={() => ai('journal')}><Sparkles size={16}/>{busy === 'journal' ? 'Writing your story…' : 'Turn my day into a story'}</button>
      <button disabled={!ready || !!busy} onClick={() => ai('title')}>Suggest a title</button><button disabled={!ready || !f.photos.length || !!busy} onClick={() => ai('captions')}>Generate photo captions</button>
      <button disabled={!f.story} onClick={() => set('story', '')}>Keep my original words</button></div>
    {f.story && <><label htmlFor="s">Your story — edit freely before saving</label><textarea id="s" value={f.story} onChange={e => set('story', e.target.value)}/>
      <label htmlFor="fe">How I felt</label><input id="fe" value={f.feelings} onChange={e => set('feelings', e.target.value)}/>
      <label htmlFor="dt">Little things to remember (one per line)</label><textarea id="dt" style={{ minHeight: 80, fontSize: '1rem' }} value={f.details.join('\n')} onChange={e => set('details', e.target.value.split('\n'))}/></>}
    <div className="bar"><button className="pri" disabled={!!busy} onClick={save}>{busy === 'save' ? 'Saving…' : 'Save memory'}</button><button onClick={() => window.history.go(0)}>Cancel</button></div></section>
}

function Library({ list, open, write, err }) {
  const [q, setQ] = useState(''), [mood, setMood] = useState(''), [act, setAct] = useState('')
  const shown = list.filter(e => (!q || JSON.stringify([e.title, e.places, e.notes, e.story, e.date]).toLowerCase().includes(q.toLowerCase())) && (!mood || e.emotions?.includes(mood)) && (!act || e.activity === act))
  return <section><h2>Your life, collected in little moments.</h2>
    <div className="bar"><button className="pri" onClick={write}>Create a new memory</button></div>
    <div className="row"><div><label htmlFor="q"><Search size={14}/> Search</label><input id="q" value={q} onChange={e => setQ(e.target.value)}/></div>
      <div><label htmlFor="m">Mood</label><select id="m" value={mood} onChange={e => setMood(e.target.value)}><option value="">Any</option>{MOODS.map(m => <option key={m}>{m}</option>)}</select></div>
      <div><label htmlFor="ac">Activity</label><select id="ac" value={act} onChange={e => setAct(e.target.value)}><option value="">Any</option>{ACT.map(a => <option key={a}>{a}</option>)}</select></div></div>
    {err && <div className="err" role="alert">{err}</div>}
    {!list.length && !err ? <div className="band"><h3>Nothing here yet</h3><p>Your first memory can be as small as a ten-minute walk. Go outside, then come back and write it down.</p></div>
      : !shown.length && list.length ? <p>No memories match those filters.</p> : <div className="grid" style={{ marginTop: '1.5rem' }}>{shown.map(e => <article className="card" key={e.id} tabIndex={0} onKeyDown={x => x.key === 'Enter' && open(e)} onClick={() => open(e)}>
        {e.photos[0] ? <img src={src(e.photos[0])} alt="" onError={x => x.target.style.visibility = 'hidden'}/> : <div className="ph"/>}<h3>{e.favorite && <Heart size={16} fill="#C47C5A" stroke="#C47C5A"/>} {e.title || 'Untitled day'}</h3>
        <p className="hand">{e.date}{e.places && ' — ' + e.places}</p><p>{(e.story || e.notes).slice(0, 120)}…</p></article>)}</div>}</section>
}

function Entry({ e, edit, gone, reload, refresh }) {
  const [msg, setMsg] = useState('')
  const fav = async () => { try { const fd = new FormData(); const d = { ...e, favorite: !e.favorite }; delete d.id; fd.append('data', JSON.stringify(d)); reload(await api('/api/journals/' + e.id, { method: 'PUT', body: fd })); refresh() } catch (x) { setMsg(x.message) } }
  const del = async () => { if (!confirm('Delete this memory and its photos? This cannot be undone.')) return; try { await api('/api/journals/' + e.id, { method: 'DELETE' }); gone() } catch (x) { setMsg(x.message) } }
  return <article>{msg && <div className="err" role="alert">{msg}</div>}<p className="hand">{e.date}{e.places && ' — ' + e.places}</p><h1 style={{ fontSize: '3rem' }}>{e.title || 'Untitled day'}</h1>
    <div className="polaroids">{e.photos.map(p => <figure className="pol" key={p.file} style={{ margin: 0 }}><img src={src(p)} alt={p.caption || 'Journal photo'} onError={x => { x.target.alt = 'Photo file is missing'; x.target.style.opacity = .3 }}/><figcaption className="hand">{p.caption}</figcaption></figure>)}</div>
    <p className="story">{e.story || e.notes}</p>
    {e.feelings && <><h3>How I felt</h3><p>{e.feelings}</p></>}{e.emotions?.length > 0 && <p className="hand">{e.emotions.join(', ')}</p>}
    {e.details?.filter(Boolean).length > 0 && <><h3>Little things I want to remember</h3><ul>{e.details.filter(Boolean).map((d, i) => <li key={i}>{d}</li>)}</ul></>}
    {e.reflection && <><h3>Reflection</h3><p>{e.reflection}</p></>}
    <div className="bar"><button onClick={edit}>Edit</button><button onClick={fav}><Heart size={16}/>{e.favorite ? 'Unfavourite' : 'Favourite'}</button><button onClick={() => window.print()}><Printer size={16}/>Print / save as PDF</button><button onClick={del}><Trash2 size={16}/>Delete</button></div></article>
}

function Explore({ start }) {
  const [i, setI] = useState(new Date().getDate() % PROMPTS.length), [on, setOn] = useState(false)
  return <section><h2>Today's invitation</h2><div className="band"><p className="story">{PROMPTS[i]}</p>
    <div className="bar">{!on ? <button className="pri" onClick={() => setOn(true)}><Footprints size={16}/>Begin</button> : <button className="pri" onClick={() => start(PROMPTS[i])}>I'm back — write it down</button>}
      <button onClick={() => { setI((i + 1) % PROMPTS.length); setOn(false) }}>Another idea</button></div></div>
    <p>Close the screen. The journal will be here when you get home.</p></section>
}
