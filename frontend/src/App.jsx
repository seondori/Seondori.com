import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip, AreaChart, Area, CartesianGrid 
} from 'recharts';
import { Globe, Cpu, TrendingUp, TrendingDown, RefreshCcw, LayoutDashboard, Settings, Search, Save, Download } from 'lucide-react';

const App = () => {
  const [activeTab, setActiveTab] = useState('indices');
  const [globalPeriod, setGlobalPeriod] = useState('1개월'); 
  const [ramPeriod, setRamPeriod] = useState('30'); // 1개월 기본
  
  // 초기값 null 유지 (로딩 상태 구분을 위해)
  const [marketData, setMarketData] = useState(null);
  const [ramData, setRamData] = useState(null);
  const [loading, setLoading] = useState(true); // 처음에 로딩 true

  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProduct, setSelectedProduct] = useState("");
  const [ramSearch, setRamSearch] = useState("");

  const [adminDate, setAdminDate] = useState(new Date().toISOString().slice(0, 10));
  const [adminTime, setAdminTime] = useState("10:00");
  const [adminText, setAdminText] = useState("");

  // 정렬 순서 (이름이 정확하지 않아도 부분 일치로 정렬 시도)
  const categoryOrder = [
    "DDR5", "DDR4", "DDR3", "노트북" 
  ];

  // 1. 시장 데이터 로드
  useEffect(() => {
    const fetchMarket = async () => {
      try {
        const res = await axios.get(`http://localhost:8000/api/market-data?period=${globalPeriod}`);
        setMarketData(res.data);
      } catch (e) { console.error(e); }
    };
    fetchMarket();
  }, [globalPeriod]);

  // 2. RAM 데이터 로드
  useEffect(() => {
    const fetchRam = async () => {
      try {
        const res = await axios.get('http://localhost:8000/api/ram-data');
        setRamData(res.data);
        setLoading(false); // 데이터 로드 완료

        // 초기값 설정
        if (res.data.current) {
            // [수정] 탭이 사라지지 않도록 데이터에 있는 모든 키를 가져옴
            const allCats = Object.keys(res.data.current);
            // 정렬
            const sortedCats = sortCategories(allCats);
            const firstCat = sortedCats[0];
            
            if (firstCat) {
                setSelectedCategory(firstCat);
                const firstProd = res.data.current[firstCat][0]?.product;
                if (firstProd) setSelectedProduct(firstProd);
            }
        }
      } catch (e) { 
          console.error(e); 
          setLoading(false);
      }
    };
    fetchRam();
  }, []);

  useEffect(() => {
    if (ramData && selectedCategory && ramData.current[selectedCategory]) {
      const items = ramData.current[selectedCategory];
      if (items && items.length > 0) {
        setSelectedProduct(items[0].product);
      }
    }
  }, [selectedCategory, ramData]);

  // [수정] 카테고리 정렬 (모든 탭 표시 보장)
  const sortCategories = (categories) => {
    return categories.sort((a, b) => {
        // 데스크탑 우선, 그 다음 DDR 버전 역순(5->4->3)
        const scoreA = (a.includes("노트북") ? 0 : 10) + (a.includes("DDR5") ? 3 : (a.includes("DDR4") ? 2 : 1));
        const scoreB = (b.includes("노트북") ? 0 : 10) + (b.includes("DDR5") ? 3 : (b.includes("DDR4") ? 2 : 1));
        return scoreB - scoreA;
    });
  };

  const handleUpdate = async () => {
    if(!adminText) return alert("데이터를 입력해주세요.");
    if(!confirm(`${adminDate} ${adminTime} 기준으로 저장하시겠습니까?`)) return;
    try {
        const res = await axios.post('http://localhost:8000/api/admin/update', {
            date: adminDate, time: adminTime, text: adminText
        });
        if (res.data.status === 'success') {
            alert("저장되었습니다.");
            setAdminText("");
            window.location.reload();
        } else { alert("실패: " + res.data.message); }
    } catch(e) { alert("서버 오류"); }
  };

  const handleDownload = () => window.open('http://localhost:8000/api/admin/download', '_blank');

  const getFilteredRamChart = () => {
    if (!ramData || !selectedProduct || !ramData.trends || !ramData.trends[selectedProduct]) return [];
    const fullHistory = ramData.trends[selectedProduct];
    const days = parseInt(ramPeriod);
    return fullHistory.slice(-days);
  };

  const getStats = (chartData) => {
    if (!chartData || chartData.length === 0) return { max: 0, min: 0, avg: 0, delta: 0, pct: 0 };
    const prices = chartData.map(d => d.price);
    const max = Math.max(...prices);
    const min = Math.min(...prices);
    const avg = Math.round(prices.reduce((a, b) => a + b, 0) / prices.length);
    const start = prices[0];
    const end = prices[prices.length - 1];
    const delta = end - start;
    const pct = (start !== 0) ? ((end - start) / start * 100) : 0;
    return { max, min, avg, start, end, delta, pct };
  };

  const renderMarketCard = (item) => {
    const isUp = item.delta >= 0;
    const chartData = item.chart || [];
    return (
      <div key={item.name} className="bg-[#1e1e1e] border border-[#333] rounded-xl p-4 flex flex-col h-48 shadow-lg">
        <div className="text-[#aaa] text-xs mb-1">{item.name}</div>
        <div className="text-2xl font-bold text-white mb-1">
          {item.current.toLocaleString(undefined, {maximumFractionDigits: 2})}
        </div>
        <div className={`text-xs flex items-center mb-4 ${isUp ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
          {isUp ? <TrendingUp size={12} className="mr-1"/> : <TrendingDown size={12} className="mr-1"/>}
          {item.delta > 0 ? '+' : ''}{item.delta.toFixed(2)} ({item.pct.toFixed(2)}%)
        </div>
        <div className="flex-1 w-full min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <Area type="monotone" dataKey="value" stroke={isUp ? "#ff5252" : "#00e676"} fill={`url(#grad${item.name})`} strokeWidth={2} isAnimationActive={false} />
              <defs>
                <linearGradient id={`grad${item.name}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isUp ? "#ff5252" : "#00e676"} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={isUp ? "#ff5252" : "#00e676"} stopOpacity={0}/>
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  };

  const getRamStats = (items) => {
    if (!items || items.length === 0) return { max: 0, min: 0, avg: 0 };
    const prices = items.map(i => i.price);
    return {
      max: Math.max(...prices),
      min: Math.min(...prices),
      avg: Math.round(prices.reduce((a, b) => a + b, 0) / prices.length)
    };
  };

  // [까만 화면 해결] 데이터 로딩 중엔 로딩 화면 표시
  if (loading || !marketData || !ramData) return (
    <div className="min-h-screen bg-[#0b0e11] text-white flex items-center justify-center font-sans">
        <div className="text-center animate-pulse"><RefreshCcw className="animate-spin mb-4 mx-auto text-blue-500" size={40}/><p>로딩 중...</p></div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#0e1117] text-white font-sans">
      <aside className="w-64 border-r border-[#333] p-6 hidden md:block bg-[#262730]">
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><Settings size={20}/> 설정</h2>
        <button onClick={() => window.location.reload()} className="w-full py-2 bg-[#333] hover:bg-[#444] rounded mb-6 text-sm flex justify-center items-center gap-2 transition">
            <RefreshCcw size={16}/> 새로고침
        </button>
        <label className="block text-sm text-gray-400 mb-2">차트 기간</label>
        <select value={globalPeriod} onChange={(e) => setGlobalPeriod(e.target.value)} className="w-full bg-[#0e1117] border border-[#555] rounded p-2 text-sm outline-none focus:border-blue-500">
            {['5일', '1개월', '6개월', '1년'].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <div className="mt-10 pt-10 border-t border-[#444]">
            <p className="text-xs text-gray-500">Version 2.1.0 (React)</p>
        </div>
      </aside>

      <main className="flex-1 p-8 overflow-y-auto">
        <header className="mb-8">
            <h1 className="text-3xl font-bold mb-2">📊 Seondori.com</h1>
        </header>

        <div className="flex gap-2 mb-6 border-b border-[#333] pb-1 overflow-x-auto">
            {[{id: 'indices', label: '📈 주가지수'}, {id: 'forex', label: '💱 환율'}, {id: 'ram', label: '💾 RAM 시세'}, {id: 'bonds', label: '💰 국채 금리'}, {id: 'admin', label: '⚙️ ADMIN'}].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-4 py-2 text-sm font-medium whitespace-nowrap rounded-t-lg transition-colors ${activeTab === tab.id ? 'bg-[#1e1e1e] text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-white'}`}>
                    {tab.label}
                </button>
            ))}
        </div>

        {activeTab !== 'ram' && activeTab !== 'admin' && marketData && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {activeTab === 'indices' && [...(marketData.indices || []), ...(marketData.macro || [])].map(renderMarketCard)}
                {activeTab === 'forex' && (marketData.forex || []).map(renderMarketCard)}
                {activeTab === 'bonds' && (marketData.bonds || []).map(renderMarketCard)}
            </div>
        )}

        {activeTab === 'ram' && ramData && (
            <div className="space-y-6">
                <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-4 mb-4 flex justify-between items-center">
                    <h3 className="font-bold text-lg">시세 히스토리</h3>
                    <select value={ramPeriod} onChange={(e)=>setRamPeriod(e.target.value)} className="bg-[#0e1117] border border-[#555] rounded px-3 py-1 text-sm outline-none">
                        <option value="5">5일</option><option value="15">15일</option><option value="30">1개월</option><option value="365">1년</option>
                    </select>
                </div>
                <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-6">
                    <div className="flex flex-wrap gap-2 mb-6">
                        {/* [수정] 데이터에 있는 모든 키를 가져와서 정렬하여 표시 (탭 사라짐 방지) */}
                        {sortCategories(Object.keys(ramData.current)).map(cat => (
                            <button key={cat} onClick={() => setSelectedCategory(cat)} className={`px-3 py-1.5 text-xs rounded border transition ${selectedCategory === cat ? 'bg-purple-600 border-purple-600 text-white' : 'bg-[#262730] border-[#444] text-gray-300 hover:bg-[#333]'}`}>
                                {cat}
                            </button>
                        ))}
                    </div>
                    <div className="overflow-x-auto max-h-60 overflow-y-auto mb-8 border border-[#333] rounded-lg">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-[#262730] text-gray-400 sticky top-0">
                                <tr><th className="py-2 px-4">제품명</th><th className="py-2 px-4 text-right">가격</th></tr>
                            </thead>
                            <tbody>
                                {ramData.current[selectedCategory]?.filter(item => item.product.toLowerCase().includes(ramSearch.toLowerCase())).map((item, i) => (
                                    <tr key={i} onClick={() => setSelectedProduct(item.product)} className={`cursor-pointer border-b border-[#333] transition ${selectedProduct === item.product ? 'bg-blue-500/20' : 'hover:bg-[#262730]'}`}>
                                        <td className="py-2 px-4">{item.product}</td>
                                        <td className="py-2 px-4 text-right font-mono text-purple-400 font-bold">{item.price_formatted}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {selectedProduct && (
                        <div className="bg-[#0e1117] rounded-xl p-6 border border-[#333]">
                            {(() => {
                                const chartData = getFilteredRamChart();
                                const stats = getStats(chartData);
                                return (
                                    <>
                                        <div className="flex justify-between items-end mb-6">
                                            <div><div className="text-sm text-gray-400 mb-1">제품</div><div className="text-xl font-bold">{selectedProduct}</div></div>
                                            <div className="text-right"><div className="text-xs text-gray-500 mb-1">변동</div><div className={`text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>{stats.delta.toLocaleString()}원 ({stats.pct.toFixed(2)}%)</div></div>
                                        </div>
                                        <div className="grid grid-cols-3 gap-4 mb-8">
                                            <div className="bg-[#1e1e1e] p-3 rounded border border-[#333] text-center"><div className="text-xs text-gray-500">최고가</div><div className="font-bold text-lg">{stats.max.toLocaleString()}원</div></div>
                                            <div className="bg-[#1e1e1e] p-3 rounded border border-[#333] text-center"><div className="text-xs text-gray-500">최저가</div><div className="font-bold text-lg">{stats.min.toLocaleString()}원</div></div>
                                            <div className="bg-[#1e1e1e] p-3 rounded border border-[#333] text-center"><div className="text-xs text-gray-500">평균가</div><div className="font-bold text-lg">{stats.avg.toLocaleString()}원</div></div>
                                        </div>
                                        <div className="h-64 w-full">
                                            <ResponsiveContainer>
                                                <LineChart data={chartData}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                                    <XAxis dataKey="date" stroke="#666" tick={{fontSize: 11}} />
                                                    <YAxis domain={['auto', 'auto']} stroke="#666" tick={{fontSize: 11}} tickFormatter={(val) => val.toLocaleString()} />
                                                    <Tooltip contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444'}} formatter={(val) => [`${val.toLocaleString()}원`, '가격']} />
                                                    <Line type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={3} dot={{r: 4, fill: '#3b82f6'}} />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </>
                                )
                            })()}
                        </div>
                    )}
                </div>
            </div>
        )}

        {/* [추가] 관리자 탭 */}
        {activeTab === 'admin' && (
            <div className="max-w-2xl mx-auto animate-in fade-in">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold flex items-center gap-2"><Save size={24} className="text-red-500"/> 데이터 업데이트</h2>
                    <button onClick={handleDownload} className="flex items-center gap-2 px-4 py-2 bg-[#262730] hover:bg-[#333] rounded text-sm transition"><Download size={16}/> 백업 다운로드</button>
                </div>
                <div className="bg-[#1e1e1e] p-6 rounded-2xl border border-[#333]">
                    <div className="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">날짜</label>
                            <input type="date" value={adminDate} onChange={(e)=>setAdminDate(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none" />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">시간</label>
                            <select value={adminTime} onChange={(e)=>setAdminTime(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none">
                                <option value="10:00">10:00 (오전)</option>
                                <option value="13:00">13:00 (점심)</option>
                                <option value="18:00">18:00 (오후)</option>
                            </select>
                        </div>
                    </div>
                    <div className="mb-6">
                        <label className="block text-sm text-gray-400 mb-2">텍스트 붙여넣기 (네이버 카페 글)</label>
                        <textarea value={adminText} onChange={(e)=>setAdminText(e.target.value)} className="w-full h-64 bg-[#0b0e11] border border-[#555] rounded p-3 text-sm resize-none outline-none font-mono" placeholder="여기에 가격 정보를 포함한 전체 텍스트를 붙여넣으세요..."></textarea>
                    </div>
                    <button onClick={handleUpdate} className="w-full py-4 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold transition">저장하기</button>
                </div>
            </div>
        )}
      </main>
    </div>
  );
};

export default App;