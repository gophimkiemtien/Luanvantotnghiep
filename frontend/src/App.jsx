import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams, useSearchParams, useLocation } from 'react-router-dom';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Search, MessageSquare, LogOut, Send, Bot, BookOpen, 
  X, Loader2, User, Lightbulb, BarChart2, Plus, 
  GraduationCap, ShieldCheck 
} from 'lucide-react';
import { XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, 
         ResponsiveContainer, AreaChart, Area, LineChart, Line, Legend } from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const ScrollToTop = () => {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
};

const SparklesIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-blue-600">
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
  </svg>
);

const SkeletonCard = () => (
  <div className="bg-white p-6 rounded-[2rem] border border-slate-200 animate-pulse">
    <div className="h-6 bg-slate-200 rounded w-3/4 mb-4"></div>
    <div className="flex gap-4 mb-4"><div className="h-4 bg-slate-200 rounded w-24"></div><div className="h-4 bg-slate-200 rounded w-32"></div></div>
    <div className="h-20 bg-slate-100 rounded-2xl"></div>
  </div>
);

const FormatOriginalAbstract = ({ text }) => {
  if (!text) return <p className="italic text-slate-400">Original abstract not found.</p>;
  let viText = text.split(/(?:\bABSTRACT\b|\bAbstract\b)/)[0];
  viText = viText.replace(/\r\n/g, '\n');
  const rawParagraphs = viText.split(/\n{2,}/);
  const cleanParagraphs = rawParagraphs
    .map(p => p.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim())
    .filter(p => p.length > 0);
  return (
    <div className="space-y-4 animate-in fade-in slide-in-from-top-4">
      <h4 className="text-[#1e5b9e] text-[10px] font-black uppercase tracking-[0.3em] mb-2 border-b border-blue-100 pb-2">
        Original Abstract
      </h4>
      {cleanParagraphs.map((para, idx) => (
        <p key={idx} className="text-justify leading-loose text-slate-700 font-serif text-[15px]">{para}</p>
      ))}
    </div>
  );
};

const LoginView = ({ onLogin }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return setError("Please enter all fields.");
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/login`, { username, password });
      onLogin(res.data);
    } catch (err) { setError("Invalid username or password."); }
    finally { setLoading(false); }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-slate-100 font-sans">
      <form onSubmit={handleSubmit} className="bg-white p-10 rounded-2xl shadow-2xl w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="bg-[#1e5b9e] w-14 h-14 rounded-2xl transform rotate-45 flex items-center justify-center mx-auto mb-4 shadow-lg"><GraduationCap size={28} className="text-white -rotate-45" /></div>
          <h2 className="text-2xl font-black text-[#002b5e] uppercase">CTU Scholar</h2>
          <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest mt-1 italic">Thesis Knowledge Mining System</p>
        </div>
        <input className="w-full border-b-2 p-3 outline-none focus:border-blue-500 text-sm" placeholder="Student ID / Username" value={username} onChange={e => setUsername(e.target.value)} />
        <input type="password" className="w-full border-b-2 p-3 outline-none focus:border-blue-500 text-sm" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} />
        {error && <p className="text-red-500 text-xs font-bold text-center italic">{error}</p>}
        <button type="submit" className="w-full bg-[#1e5b9e] text-white p-3.5 rounded-xl font-black uppercase hover:bg-[#15467a] shadow-md">{loading ? "Processing..." : "Login"}</button>
      </form>
    </div>
  );
};

const Header = ({ user, onLogout, setAssistantOpen }) => {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchTerm.trim()) navigate(`/search?q=${encodeURIComponent(searchTerm)}`);
  };

  return (
    <header className="h-20 flex items-center justify-between px-8 bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
      <div className="flex items-center gap-4 cursor-pointer group" onClick={() => navigate('/')}>
        <div className="bg-[#1e5b9e] p-2 rounded-xl rotate-45 group-hover:scale-110 transition-transform"><GraduationCap size={24} className="text-white -rotate-45" /></div>
        <span className="font-black text-2xl text-[#002b5e] uppercase italic tracking-tighter">CTU Scholar</span>
      </div>
      <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-lg ml-10 relative">
        <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className="w-full bg-slate-100 border-none rounded-full py-3 pl-6 pr-14 outline-none font-black text-sm text-slate-700 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all" placeholder="Search theses..." />
        <button className="absolute right-2 top-2 bottom-2 w-10 bg-[#1e5b9e] text-white rounded-full flex justify-center items-center shadow-md hover:bg-blue-800"><Search size={16}/></button>
      </form>
      <div className="flex gap-6 font-black uppercase text-[10px] tracking-[0.2em] text-[#002b5e] items-center">
        <button onClick={() => navigate('/trends')} className="flex items-center gap-2 hover:text-blue-500 transition-colors"><BarChart2 size={16}/> Trends</button>
        {user.role !== 'Sinh viên' && (
          <button onClick={() => navigate('/novelty')} className="flex items-center gap-2 hover:text-blue-500 transition-colors"><ShieldCheck size={16}/> Novelty Check</button>
        )}
        <button onClick={() => setAssistantOpen(true)} className="flex items-center gap-2 hover:text-blue-500 transition-colors"><MessageSquare size={16}/> Global Assistant</button>
        <div className="flex items-center gap-4 border-l border-slate-200 pl-6">
          <div className="text-right hidden xl:block"><div className="text-[11px] text-slate-800">{user.username}</div><div className="text-[9px] text-blue-500 opacity-60">{user.role === 'Sinh viên' ? 'Student' : user.role}</div></div>
          <button onClick={onLogout} className="p-2.5 bg-slate-50 border border-slate-200 text-slate-500 rounded-xl hover:text-red-600 hover:bg-red-50 transition-all"><LogOut size={16}/></button>
        </div>
      </div>
    </header>
  );
};

const AcademicAssistant = ({ user, isOpen, onClose }) => {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [chat, setChat] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef();

  const loadSessions = () => axios.get(`${API_BASE}/chat-sessions/${user.id}`).then(res => setSessions(res.data));
  useEffect(() => { if (isOpen) loadSessions(); }, [isOpen]);
  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat]);

  const selectSession = (sId) => {
    setCurrentSessionId(sId);
    axios.get(`${API_BASE}/chat-history/${sId}`).then(res => setChat(res.data));
  };
  const startNewChat = () => { setCurrentSessionId(null); setChat([]); setInput(""); };

  const handleSend = async (e) => {
    e.preventDefault(); if (!input.trim()) return;
    const msg = input; setInput(""); setChat(prev => [...prev, { role: 'user', text: msg }]); setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/global-chat`, { user_id: user.id, message: msg, session_id: currentSessionId });
      setChat(prev => [...prev, { role: 'bot', text: res.data.answer, sources: res.data.sources }]);
      if (!currentSessionId) { setCurrentSessionId(res.data.session_id); loadSessions(); }
    } catch (err) {
      let errMsg = "❌ Connection error.";
      if(err.response && err.response.status === 429) errMsg = "❌ Warning: AI quota exceeded.";
      setChat(prev => [...prev, { role: 'bot', text: errMsg }]);
    } finally { setLoading(false); }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex animate-in fade-in">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative flex w-full max-w-5xl mx-auto my-6 bg-white rounded-[2rem] shadow-2xl overflow-hidden border">
        <div className="w-72 bg-slate-50 border-r flex flex-col font-sans">
          <div className="p-4 border-b"><button onClick={startNewChat} className="w-full py-3 bg-[#1e5b9e] text-white rounded-xl font-bold text-xs uppercase flex items-center justify-center gap-2 hover:bg-[#15467a] transition-all"><Plus size={16}/> New Chat</button></div>
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            {sessions.map(s => (
              <div key={s.session_id} onClick={() => selectSession(s.session_id)} className={`p-3 rounded-xl text-xs font-bold cursor-pointer transition-all ${currentSessionId === s.session_id ? 'bg-blue-100 text-blue-700' : 'text-slate-500 hover:bg-slate-200'}`}>
                <span className="line-clamp-1">"{s.title}"</span>
              </div>
            ))}
          </div>
        </div>
        <div className="flex-1 flex flex-col bg-white">
          <div className="p-5 border-b flex justify-between items-center font-black text-[#1e5b9e] uppercase italic tracking-widest"><h3>Scholar Assistant</h3><button onClick={onClose}><X size={20}/></button></div>
          <div className="flex-1 p-8 overflow-y-auto space-y-6 bg-slate-50/50">
            {chat.map((c, i) => (
              <div key={i} className={`flex ${c.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-5 rounded-2xl text-[14px] leading-relaxed shadow-sm ${c.role === 'user' ? 'bg-[#1e5b9e] text-white rounded-tr-none' : 'bg-white border font-medium text-slate-700'}`}>
                  {c.role === 'bot' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{c.text}</ReactMarkdown> : c.text}
                </div>
              </div>
            ))}
            {loading && <div className="animate-pulse flex gap-2 text-xs text-slate-400 font-bold"><Loader2 size={14} className="animate-spin"/> AI is analyzing...</div>}
            <div ref={scrollRef} />
          </div>
          <form onSubmit={handleSend} className="p-6 border-t bg-white flex gap-4"><input className="flex-1 p-4 bg-slate-50 border rounded-2xl outline-none text-sm font-bold" placeholder="Ask AI..." value={input} onChange={e => setInput(e.target.value)} /><button className="bg-[#1e5b9e] p-4 rounded-2xl text-white shadow-xl hover:bg-[#15467a]"><Send size={20}/></button></form>
        </div>
      </div>
    </div>
  );
};

const SearchResultItem = ({ thesis, onClick, onMajorClick }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="bg-white p-6 rounded-[2rem] border border-slate-200 shadow-sm hover:shadow-lg hover:border-blue-300 transition-all duration-300 mb-6 group relative overflow-hidden">
      <div className="absolute top-0 right-0 bg-slate-50 px-5 py-2 rounded-bl-[2rem] text-[10px] font-black text-slate-400 uppercase tracking-widest border-l border-b border-slate-100">COHORT {thesis.year || 'N/A'}</div>
      <h3 onClick={onClick} className="text-xl font-black text-slate-800 group-hover:text-[#1e5b9e] mb-4 uppercase italic tracking-tighter pr-20 cursor-pointer leading-tight transition-colors">"{thesis.title}"</h3>
      <div className="flex items-center gap-6 text-[10px] text-slate-500 mb-6 font-black uppercase tracking-widest">
        <span className="flex items-center gap-2"><User size={14} className="text-blue-500"/> {thesis.author || 'Unknown'}</span>
        <span className="text-slate-200">|</span>
        <span className="flex items-center gap-2 cursor-pointer hover:text-blue-600 hover:underline" onClick={(e) => { e.stopPropagation(); onMajorClick(thesis.major || thesis.standard_major); }}><BookOpen size={14} className="text-blue-500"/> {thesis.major || thesis.standard_major || 'N/A'}</span>
      </div>
      <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100 shadow-inner">
        <div className="flex items-center gap-3 mb-2"><span className="font-black text-[#1e5b9e] uppercase text-[9px] bg-[#e2eefc] px-3 py-1 rounded-full shadow-sm flex items-center gap-1"><SparklesIcon /> AI SUMMARY</span></div>
        <p className="text-[14px] text-slate-600 leading-relaxed font-medium italic">{thesis.ai_tldr || "AI Summary not available for this thesis."}</p>
        
        {thesis.original_abstract && (
          <div className="mt-4 pt-4 border-t border-slate-200">
            <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} className="text-[11px] font-black text-[#1e5b9e] hover:underline uppercase tracking-widest flex items-center gap-1">{expanded ? "Hide abstract" : "Read original abstract"}</button>
            {expanded && (
              <div className="mt-4 bg-white p-4 rounded-xl border border-slate-200">
                <FormatOriginalAbstract text={thesis.original_abstract} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const DetailView = () => {
  const { fileName } = useParams();
  const navigate = useNavigate();
  const [thesis, setThesis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('topics');
  const [recs, setRecs] = useState([]);
  const [gapData, setGapData] = useState(null);
  const [expandedAbstract, setExpandedAbstract] = useState(false);
  const [loadingGap, setLoadingGap] = useState(false);
  const [chat, setChat] = useState([]);
  const [input, setInput] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const chatScrollRef = useRef();

  useEffect(() => {
    const fetchThesis = async () => {
      try {
        const res = await axios.get(`${API_BASE}/thesis/${encodeURIComponent(fileName)}`);
        setThesis(res.data);
      } catch (err) { navigate('/'); } 
      finally { setLoading(false); }
    };
    fetchThesis();
  }, [fileName, navigate]);

  useEffect(() => {
    if (thesis) axios.get(`${API_BASE}/recommend/${thesis.file_name}`).then(res => setRecs(res.data || []));
  }, [thesis]);

  useEffect(() => {
    if (tab === 'ideation' && thesis && !gapData) {
      setLoadingGap(true);
      axios.get(`${API_BASE}/research-gap/${thesis.file_name}`).then(res => setGapData(res.data)).finally(() => setLoadingGap(false));
    }
  }, [tab, thesis, gapData]);

  useEffect(() => {
    if (fileName) {
      const saved = localStorage.getItem(`local_chat_${fileName}`);
      if (saved) setChat(JSON.parse(saved));
      else setChat([]);
    }
  }, [fileName]);

  useEffect(() => {
    if (fileName && chat.length) localStorage.setItem(`local_chat_${fileName}`, JSON.stringify(chat));
  }, [chat, fileName]);

  useEffect(() => { chatScrollRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat]);

  const handleLocalChat = async (e) => {
    e.preventDefault(); if (!input.trim()) return;
    const msg = input; setInput(""); setChat(prev => [...prev, { role: 'user', text: msg }]); setLoadingChat(true);
    try {
      const res = await axios.post(`${API_BASE}/ask`, { query: msg, file_name: fileName, top_k: 4 });
      setChat(prev => [...prev, { role: 'bot', text: res.data.answer, sources: res.data.sources || [] }]);
    } catch (err) {
      setChat(prev => [...prev, { role: 'bot', text: "AI Error." }]);
    } finally { setLoadingChat(false); }
  };

  if (loading || !thesis) return <div className="flex justify-center py-20"><Loader2 className="animate-spin text-blue-500" size={50}/></div>;

  return (
    <div className="w-full max-w-[1400px] mx-auto px-6 py-8 flex flex-col lg:flex-row gap-8 animate-in slide-in-from-bottom-8">
      <div className="lg:w-[68%] w-full bg-white rounded-[3rem] p-10 border border-slate-100 shadow-2xl shadow-blue-900/5">
        <button onClick={() => navigate(-1)} className="text-slate-400 font-black text-[10px] mb-8 uppercase tracking-widest hover:text-blue-500">← Go back</button>
        <h1 className="text-4xl font-black text-slate-800 italic uppercase mb-6 leading-tight tracking-tighter">"{thesis.title}"</h1>
        <div className="flex flex-wrap gap-4 text-xs font-bold text-slate-500 mb-8 uppercase tracking-widest">
          <span className="text-blue-600 bg-blue-50 px-3 py-1 rounded-md">{thesis.author}</span>
          <span className="bg-slate-50 px-3 py-1 rounded-md cursor-pointer hover:bg-slate-100" onClick={() => navigate(`/search?q=${encodeURIComponent(thesis.major || thesis.standard_major)}`)}>{thesis.major || thesis.standard_major}</span>
          <span className="bg-slate-50 px-3 py-1 rounded-md">Cohort {thesis.year}</span>
        </div>
        <div className="bg-[#e2eefc] p-8 rounded-[2rem] text-slate-700 mb-8 font-medium shadow-inner">
          <h3 className="text-[#1e5b9e] text-[10px] font-black uppercase tracking-[0.3em] mb-4 flex items-center gap-2"><SparklesIcon/> AI Summary</h3>
          <p className="leading-relaxed text-[15px] italic font-bold">{thesis.ai_tldr}</p>
          {expandedAbstract && (
            <div className="mt-6 pt-6 border-t border-blue-200">
              <FormatOriginalAbstract text={thesis.original_abstract} />
            </div>
          )}
          {thesis.original_abstract && (
            <button onClick={() => setExpandedAbstract(!expandedAbstract)} className="mt-6 bg-white border border-blue-200 text-[#1e5b9e] font-black text-[10px] uppercase tracking-widest px-6 py-2 rounded-full hover:shadow-md transition-all">{expandedAbstract ? "Hide Abstract" : "Read Original Abstract"}</button>
          )}
        </div>
        <div className="flex flex-wrap gap-6 border-b mb-8 font-black uppercase text-[10px] tracking-widest">
          <button onClick={()=>setTab('topics')} className={`pb-4 ${tab==='topics' ? 'border-b-4 border-blue-500 text-blue-600' : 'text-slate-400 hover:text-slate-600'}`}>Keywords</button>
          <button onClick={()=>setTab('ideation')} className={`pb-4 ${tab==='ideation' ? 'border-b-4 border-amber-500 text-amber-600' : 'text-slate-400 hover:text-slate-600'}`}>Research Gap</button>
          <button onClick={()=>setTab('related')} className={`pb-4 ${tab==='related' ? 'border-b-4 border-blue-500 text-blue-600' : 'text-slate-400 hover:text-slate-600'}`}>Related Theses</button>
        </div>
        <div className="min-h-[200px]">
          {tab === 'topics' && (
            <div className="flex flex-wrap gap-4 animate-in fade-in">
              {thesis.keywords?.map(k => (
                <button key={k} onClick={() => navigate(`/topic/${encodeURIComponent(k)}`)} className="px-6 py-3 bg-slate-50 border border-slate-200 shadow-sm rounded-full text-xs font-bold text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-colors uppercase tracking-widest">{k}</button>
              ))}
              {(!thesis.keywords || thesis.keywords.length === 0) && <p className="text-slate-400 italic font-bold">No keyword data available.</p>}
            </div>
          )}
          {tab === 'ideation' && (
            <div className="p-8 bg-amber-50 rounded-[2rem] border border-amber-100 font-bold text-amber-900 whitespace-pre-line leading-relaxed text-[15px] animate-in fade-in shadow-inner">
              {loadingGap ? <div className="flex gap-2 text-amber-600 justify-center"><Loader2 className="animate-spin"/> AI is analyzing research gap...</div> : (
                <>
                  <p className="mb-4">{gapData?.limitations}</p>
                  <div className="mt-4"><strong>Future Research Directions:</strong><ul className="list-disc pl-6 mt-2">{gapData?.future_works?.map((w, i) => <li key={i}>{w}</li>)}</ul></div>
                </>
              )}
            </div>
          )}
          {tab === 'related' && (
            <div className="space-y-4 animate-in fade-in">
              {recs.map((r, i) => (
                <div key={i} onClick={() => navigate(`/thesis/${r.file_name}`)} className="p-6 border border-slate-100 rounded-2xl hover:border-blue-500 cursor-pointer bg-slate-50 shadow-sm group">
                  <h4 className="font-black italic text-slate-700 uppercase group-hover:text-blue-600 mb-2">"{r.title}"</h4>
                  <p className="text-[10px] uppercase font-bold text-slate-400 tracking-widest">{r.author} • COHORT {r.year}</p>
                </div>
              ))}
              {recs.length === 0 && <p className="text-slate-400 italic font-bold">Searching for related documents...</p>}
            </div>
          )}
        </div>
      </div>
      <div className="lg:w-[32%] w-full flex flex-col bg-slate-50 rounded-[3rem] border border-slate-200 shadow-2xl h-[calc(100vh-120px)] lg:sticky lg:top-24 overflow-hidden">
        <div className="p-6 bg-white border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3"><div className="bg-[#1e5b9e] p-2.5 rounded-xl text-white shadow-md"><MessageSquare size={18}/></div><div><h3 className="text-xs font-black text-[#002b5e] uppercase tracking-widest">Document Assistant</h3><p className="text-[9px] font-bold text-green-600 uppercase tracking-widest">● Document Connected</p></div></div>
        </div>
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          {chat.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center opacity-30 text-center"><Bot size={60} className="mb-4 text-[#1e5b9e]"/><p className="text-[11px] font-black uppercase tracking-widest italic text-slate-500">Ask about the methods,<br/>tools, or results of<br/>this thesis.</p></div>
          )}
          {chat.map((c, i) => (
            <div key={i} className={`flex ${c.role==='user'?'justify-end':'justify-start'}`}>
              <div className={`p-4 rounded-2xl text-[13px] leading-relaxed shadow-sm max-w-[90%] ${c.role==='user'?'bg-[#1e5b9e] text-white rounded-tr-none':'bg-white border border-slate-200 text-slate-700 font-medium rounded-tl-none'}`}>
                {c.role === 'bot' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{c.text}</ReactMarkdown> : c.text}
              </div>
            </div>
          ))}
          {loadingChat && <div className="flex justify-start"><div className="bg-white border border-slate-200 p-3 rounded-2xl rounded-tl-none flex items-center gap-2"><Loader2 size={14} className="animate-spin text-[#1e5b9e]"/><span className="text-[10px] font-black italic text-[#1e5b9e] uppercase tracking-widest">AI is reading...</span></div></div>}
          <div ref={chatScrollRef} />
        </div>
        <form onSubmit={handleLocalChat} className="p-4 bg-white border-t border-slate-200 flex gap-3">
          <input className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 outline-none text-[13px] font-medium focus:ring-2 focus:ring-blue-100" placeholder="Ask AI..." value={input} onChange={e=>setInput(e.target.value)} />
          <button className="bg-[#1e5b9e] text-white p-3 rounded-xl shadow-md hover:bg-[#15467a] transition-colors"><Send size={18}/></button>
        </form>
      </div>
    </div>
  );
};

// ---------- TOPIC VIEW ----------
const TopicView = () => {
  const { topicName } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [theses, setTheses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const resT = await axios.get(`${API_BASE}/topic/${encodeURIComponent(topicName)}`); 
        setData(resT.data);
        const resTh = await axios.post(`${API_BASE}/semantic-search`, { query: topicName, limit: 5 }); 
        setTheses(resTh.data.results || []);
      } catch (e) {} finally { setLoading(false); }
    }; fetch();
  }, [topicName]);

  if (loading) return <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" size={50}/></div>;
  
  return (
    <div className="max-w-5xl mx-auto py-10 px-6 animate-in fade-in">
      <button onClick={() => navigate(-1)} className="text-blue-600 font-black text-[10px] uppercase mb-8 tracking-widest hover:underline">← Go back</button>
      <h1 className="text-4xl font-black text-[#1e5b9e] uppercase italic mb-8 border-l-8 border-[#ffc107] pl-6 tracking-tighter">{topicName}</h1>
      
      {/* 🔴 ĐÃ FIX: Sử dụng ReactMarkdown để render định dạng và gỡ bỏ class ép in đậm/in nghiêng toàn khối */}
      <div className="bg-slate-50 border p-8 rounded-[2rem] mb-10 text-slate-700 text-[15px] leading-relaxed shadow-inner">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom lại CSS cho từng thẻ Markdown để nó đẹp như ý muốn
            p: ({node, ...props}) => <p className="mb-4 text-justify" {...props} />,
            ul: ({node, ...props}) => <ul className="list-disc pl-6 mb-4 space-y-2" {...props} />,
            ol: ({node, ...props}) => <ol className="list-decimal pl-6 mb-4 space-y-2" {...props} />,
            li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
            strong: ({node, ...props}) => <strong className="font-black text-[#1e5b9e]" {...props} />,
          }}
        >
          {data?.definition || ''}
        </ReactMarkdown>
      </div>

      <h3 className="font-black text-xl italic mb-6 uppercase text-slate-800">Featured Theses</h3>
      <div className="space-y-4">
        {theses.map((t,i) => (
          <div key={i} onClick={() => navigate(`/thesis/${t.file_name}`)} className="p-6 border border-slate-200 rounded-2xl cursor-pointer hover:border-blue-500 bg-white font-black italic uppercase text-slate-700 shadow-sm hover:shadow-md transition-all group">
            <span className="group-hover:text-blue-600">"{t.title}"</span>
            <div className="text-[10px] text-slate-400 mt-2 tracking-widest">{t.author} • COHORT {t.year}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ---------- SEARCH VIEW (Đã khôi phục Phân Trang) ----------
const SearchView = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get('q') || '';
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Biến quản lý phân trang
  const [page, setPage] = useState(1);
  const pageSize = 5; // Số bài luận văn hiển thị trên mỗi trang

  useEffect(() => {
    if (!query) return;
    setLoading(true);
    setPage(1); // Reset về trang 1 mỗi khi gõ từ khóa mới

    // Gọi API lấy 50 bài tốt nhất về để chia trang
    axios.post(`${API_BASE}/semantic-search`, { query, limit: 150 }).then(res => {
      setResults(res.data.results || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [query]);

  // Logic cắt mảng để hiển thị theo trang
  const paginated = results.slice((page-1)*pageSize, page*pageSize);
  const totalPages = Math.ceil(results.length / pageSize);

  return (
    <div className="max-w-5xl mx-auto py-12 px-6 animate-in fade-in">
      <h2 className="text-xl font-black text-[#002b5e] mb-10 uppercase italic border-l-4 border-amber-500 pl-4">
        {loading ? "Scanning knowledge base..." : `RESULTS FOR: "${query}" (${results.length} theses)`}
      </h2>
      
      {loading ? (
        <div className="space-y-6"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : (
        <>
          {paginated.length === 0 ? (
            <div className="text-center py-20 text-slate-400 font-bold italic">No matching theses found. Please try different keywords.</div>
          ) : (
            paginated.map((t, i) => (
              <SearchResultItem 
                key={i} 
                thesis={t} 
                onClick={() => navigate(`/thesis/${t.file_name}`)} 
                onMajorClick={(major) => navigate(`/search?q=${encodeURIComponent(major)}`)} 
              />
            ))
          )}
          
          {/* Thanh phân trang (Chỉ hiện khi có nhiều hơn 1 trang) */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center gap-4 mt-12 mb-8">
              <button 
                disabled={page === 1} 
                onClick={() => { setPage(p => p - 1); window.scrollTo(0, 0); }} 
                className="px-5 py-2.5 bg-white border border-slate-200 shadow-sm rounded-full disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-black text-[#1e5b9e] hover:bg-slate-50 uppercase tracking-widest transition-all"
              >
                « Prev
              </button>
              
              <span className="px-4 py-2 text-[11px] text-slate-500 font-black uppercase tracking-widest bg-slate-100 rounded-full">
                Page {page} / {totalPages}
              </span>
              
              <button 
                disabled={page === totalPages} 
                onClick={() => { setPage(p => p + 1); window.scrollTo(0, 0); }} 
                className="px-5 py-2.5 bg-white border border-slate-200 shadow-sm rounded-full disabled:opacity-40 disabled:cursor-not-allowed text-[11px] font-black text-[#1e5b9e] hover:bg-slate-50 uppercase tracking-widest transition-all"
              >
                Next »
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

const TrendsAnalysisView = () => {
  const [areaData, setAreaData] = useState([]);
  const [lineData, setLineData] = useState([]);
  const [kws, setKws] = useState([]);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([
      axios.get(`${API_BASE}/trends`),
      axios.get(`${API_BASE}/keyword-growth`),
      axios.get(`${API_BASE}/trend-insights`)
    ]).then(([resA, resL, resI]) => {
      setAreaData(resA.data);
      setLineData(resL.data.chart_data);
      setKws(resL.data.keywords);
      setInsights(resI.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const colors = ["#1e5b9e", "#ffc107", "#4caf50", "#f44336", "#9c27b0"];
  return (
    <div className="max-w-6xl mx-auto px-6 py-10 animate-in fade-in duration-700">
      <button onClick={() => navigate('/')} className="mb-8 px-6 py-2 bg-white border rounded-full text-[10px] font-black text-[#1e5b9e] uppercase tracking-widest shadow-sm hover:shadow-md transition-all">← Home</button>
      <div className="mb-12 border-l-8 border-[#ffc107] pl-6"><h1 className="text-4xl font-black text-[#002b5e] uppercase italic tracking-tighter">Trend Discovery</h1></div>
      {loading ? <div className="flex justify-center py-20"><Loader2 className="animate-spin text-blue-500" size={50}/></div> : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <div className="bg-white p-8 rounded-[2rem] border shadow-xl shadow-blue-900/5">
              <h3 className="text-[10px] font-black text-slate-400 uppercase mb-8 tracking-widest flex items-center gap-2"><BarChart2 size={16}/> Total Thesis Output</h3>
              <div className="h-[300px]"><ResponsiveContainer><AreaChart data={areaData}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="year" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 13, fontWeight: 'bold'}} /><YAxis hide /><RechartsTooltip /><Area type="monotone" dataKey="count" stroke="#1e5b9e" strokeWidth={4} fill="#e2eefc" /></AreaChart></ResponsiveContainer></div>
            </div>
            <div className="bg-white p-8 rounded-[2rem] border shadow-xl shadow-blue-900/5">
              <h3 className="text-[10px] font-black text-slate-400 uppercase mb-8 tracking-widest flex items-center gap-2"><BarChart2 size={16}/> Topic Growth Rate</h3>
              <div className="h-[300px]"><ResponsiveContainer><LineChart data={lineData}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="year" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 13, fontWeight: 'bold'}}/><YAxis hide /><RechartsTooltip /><Legend iconType="circle" />{kws.map((kw, i) => <Line key={kw} type="monotone" dataKey={kw} stroke={colors[i%colors.length]} strokeWidth={3} activeDot={{r:8}}/>)}</LineChart></ResponsiveContainer></div>
            </div>
          </div>
          <div className="bg-[#002b5e] p-8 rounded-[2rem] text-white shadow-2xl relative overflow-hidden group">
            <Bot size={150} className="absolute -right-10 -bottom-10 opacity-10 group-hover:scale-110 transition-transform duration-700"/>
            <h3 className="text-[10px] font-black uppercase mb-4 opacity-50 tracking-[0.3em] flex items-center gap-2"><Lightbulb size={14} className="text-amber-400"/> AI Insights</h3>
            <p className="text-lg font-bold italic mb-6 leading-relaxed">{insights?.analysis}</p>
            <div className="flex flex-wrap gap-4">{insights?.suggestions?.map((s, i) => <span key={i} className="bg-white/10 px-4 py-2 rounded-xl text-xs font-bold border border-white/20 uppercase tracking-widest">{s}</span>)}</div>
          </div>
        </>
      )}
    </div>
  );
};

const NoveltyCheckView = () => {
  const [abstract, setAbstract] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleCheck = async () => {
    if (!abstract.trim()) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/check-novelty`, { abstract, top_k: 5 });
      setResult(res.data);
    } catch (err) { alert('Error: ' + (err.response?.data?.detail || err.message)); }
    finally { setLoading(false); }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 animate-in fade-in">
      <button onClick={() => navigate('/')} className="mb-8 px-6 py-2 bg-white border rounded-full text-[10px] font-black text-[#1e5b9e] uppercase tracking-widest shadow-sm hover:shadow-md">← Home</button>
      <div className="mb-12 border-l-8 border-amber-500 pl-6"><h1 className="text-4xl font-black text-[#002b5e] uppercase italic tracking-tighter">Novelty Check</h1></div>
      <div className="bg-white rounded-[2rem] border p-8 shadow-xl">
        <textarea rows={8} className="w-full p-5 border rounded-xl focus:ring-2 focus:ring-blue-100 outline-none font-medium" placeholder="Paste thesis abstract here to check for novelty..." value={abstract} onChange={e => setAbstract(e.target.value)} />
        <button onClick={handleCheck} disabled={loading} className="mt-6 bg-[#1e5b9e] text-white px-8 py-3 rounded-full font-black uppercase tracking-widest text-xs hover:bg-[#15467a] transition-colors">{loading && <Loader2 size={18} className="animate-spin inline mr-2"/>}Analyze</button>
        {result && (
          <div className="mt-8 p-6 bg-slate-50 rounded-2xl border">
            {result.is_novel ? <div className="bg-green-100 text-green-700 p-3 rounded-xl font-bold flex items-center gap-2">✅ NOVEL – No similar theses found</div> : <div className="bg-red-100 text-red-700 p-3 rounded-xl font-bold flex items-center gap-2">⚠️ WARNING – Similar theses found</div>}
            {result.similar_theses?.length > 0 && (
              <div className="mt-4 space-y-2">
                <h4 className="font-black text-xs uppercase tracking-widest text-slate-500">Overlapping Theses:</h4>
                {result.similar_theses.map((t, i) => (
                  <div key={i} className="bg-white p-4 rounded-xl border"><p className="font-bold italic">"{t.title}"</p><p className="text-xs text-slate-500">{t.author} • {t.year} • Similarity: {(t.score * 100).toFixed(1)}%</p></div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const HomeView = () => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[85vh] px-6 animate-in fade-in duration-1000">
      <div className="bg-[#e2eefc] p-6 rounded-[2.5rem] shadow-lg border border-blue-50 mb-8 transform -rotate-3 hover:rotate-0 transition-all duration-700"><GraduationCap size={70} className="text-[#1e5b9e]"/></div>
      <h1 className="text-6xl font-black text-[#002b5e] uppercase italic mb-8 tracking-tighter">CTU Scholar</h1>
      <form onSubmit={handleSearch} className="w-full max-w-2xl flex border border-slate-200 rounded-[1.5rem] bg-white shadow-xl overflow-hidden hover:shadow-2xl transition-shadow">
        <input value={query} onChange={e=>setQuery(e.target.value)} className="flex-1 p-6 text-xl font-bold outline-none text-slate-700" placeholder="Ask or search for theses..." />
        <button className="bg-[#1e5b9e] text-white px-10 hover:bg-[#15467a] transition-colors flex items-center justify-center"><Search size={28} strokeWidth={3}/></button>
      </form>
      <div className="mt-10 flex items-center gap-6 text-[11px] font-black uppercase tracking-[0.3em] opacity-40"><span>Suggestions:</span><div className="flex gap-4 font-black">{["Deep Learning", "RAG", "Digital Economy"].map(t => (<button key={t} onClick={() => navigate(`/search?q=${encodeURIComponent(t)}`)} className="hover:text-blue-500 transition-all underline decoration-blue-200 underline-offset-4">{t}</button>))}</div></div>
    </div>
  );
};

export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [assistantOpen, setAssistantOpen] = useState(false);

  const handleLogin = (userData) => {
    setUser(userData);
    localStorage.setItem('user', JSON.stringify(userData));
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('user');
  };

  if (!user) return <LoginView onLogin={handleLogin} />;

  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="min-h-screen flex flex-col bg-slate-50 font-sans text-slate-900 selection:bg-blue-100">
        <Header user={user} onLogout={handleLogout} setAssistantOpen={setAssistantOpen} />
        <AcademicAssistant user={user} isOpen={assistantOpen} onClose={() => setAssistantOpen(false)} />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<HomeView />} />
            <Route path="/search" element={<SearchView />} />
            <Route path="/thesis/:fileName" element={<DetailView />} />
            <Route path="/trends" element={<TrendsAnalysisView />} />
            <Route path="/novelty" element={<NoveltyCheckView />} />
            <Route path="/topic/:topicName" element={<TopicView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}