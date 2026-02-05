import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip, AreaChart, Area, CartesianGrid 
} from 'recharts';
import { Globe, Cpu, TrendingUp, TrendingDown, RefreshCcw, LayoutDashboard, Settings, Search, Save, Download } from 'lucide-react';

const App = () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [data, setData] = useState({ market: {}, ram: {}, history: {} });
  const [activeTab, setActiveTab] = useState('ram');  // ✅ RAM 시세가 기본 탭
  const [loading, setLoading] = useState(false);
  
  const [globalPeriod, setGlobalPeriod] = useState('1개월');
  const [ramPeriod, setRamPeriod] = useState('30'); 

  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProduct, setSelectedProduct] = useState("");
  const [ramSearch, setRamSearch] = useState("");

  const [adminDate, setAdminDate] = useState(new Date().toISOString().slice(0, 10));
  const [adminTime, setAdminTime] = useState("10:00");
  const [adminText, setAdminText] = useState("");
  const [parseLog, setParseLog] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [marketRes, ramRes] = await Promise.all([
        axios.get(`${API_URL}/api/market-data?period=${globalPeriod}`),
        axios.get(`${API_URL}/api/ram-data`)
      ]);
      
      console.log("RAM Data Response:", ramRes.data);
      
      setData({
        market: marketRes.data,
        ram: ramRes.data.current || {},
        history: ramRes.data.trends || {}
      });
      
      if (ramRes.data.current) {
        const availableCats = Object.keys(ramRes.data.current);
        console.log("Available categories:", availableCats);
        const sortedCats = sortCategories(availableCats);
        const firstCat = sortedCats[0];
        
        if (firstCat) {
            setSelectedCategory(firstCat);
            const firstProd = ramRes.data.current[firstCat][0]?.product;
            if (firstProd) setSelectedProduct(firstProd);
        }
      }
    } catch (err) { 
      console.error("Data fetch error:", err); 
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    if (activeTab === 'tradingview') {
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/tv.js';
      script.async = true;
      script.onload = () => {
        if (window.TradingView) {
          new window.TradingView.widget({
            autosize: true,
            symbol: "FX_IDC:USDKRW",
            interval: "D",
            timezone: "Asia/Seoul",
            theme: "dark",
            style: "1",
            locale: "kr",
            toolbar_bg: "#1e1e1e",
            enable_publishing: false,
            hide_side_toolbar: false,
            allow_symbol_change: true,
            studies: ["RSI@tv-basicstudies"],
            container_id: "tradingview_chart"
          });
        }
      };
      document.body.appendChild(script);
      
      return () => {
        if (document.body.contains(script)) {
          document.body.removeChild(script);
        }
      };
    }
  }, [activeTab]);

  const sortCategories = (categories) => {
    const order = [
      "DDR5 RAM (데스크탑)",
      "DDR4 RAM (데스크탑)",
      "DDR3 RAM (데스크탑)",
      "DDR5 RAM (노트북)",
      "DDR4 RAM (노트북)",
      "DDR3 RAM (노트북)"
    ];
    
    return categories.sort((a, b) => {
      const indexA = order.indexOf(a);
      const indexB = order.indexOf(b);
      if (indexA === -1 && indexB === -1) return a.localeCompare(b);
      if (indexA === -1) return 1;
      if (indexB === -1) return -1;
      return indexA - indexB;
    });
  };

  const handleUpdate = async () => {
    if(!adminText) return alert("데이터를 입력해주세요.");
    if(!confirm(`${adminDate} ${adminTime} 기준으로 저장하시겠습니까?`)) return;
    try {
        const res = await axios.post(`${API_URL}/api/admin/update`, {
            date: adminDate,
            time: adminTime,
            text: adminText
        });
        if (res.data.status === 'success') {
            alert(`✅ 성공!\n- ${res.data.count}개 항목 저장됨\n- 총 ${res.data.total_categories}개 카테고리\n- ${res.data.message}`);
            setAdminText("");
            setParseLog(`마지막 업데이트: ${adminDate} ${adminTime} (${res.data.count}개 항목)`);
            setTimeout(() => fetchData(), 1000);
        } else { alert("실패: " + res.data.message); }
    } catch(e) { alert("서버 오류: " + e.message); }
  };

  const handleDownload = () => {
    window.open(`${API_URL}/api/admin/download`, '_blank');
  };

  // ============================================
  // RAM 트렌드 데이터 - 기간 필터링 적용
  // ============================================
  const getRamTrend = (category, productName) => {
    if (!data.history) return [];
    
    const productTrend = data.history[productName];
    if (!productTrend || !Array.isArray(productTrend)) return [];
    
    // 선택한 기간만큼 슬라이스
    const periodDays = parseInt(ramPeriod);
    const slicedData = productTrend.slice(-periodDays);
    
    return slicedData.map(item => ({
      name: item.date.length > 10 ? item.date.substring(5, 16) : item.date.substring(5),
      price: item.price
    }));
  };

  // ============================================
  // [핵심 수정] 통계 계산 - 첫날 vs 마지막날 비교
  // ============================================
  const getStats = (chartData) => {
    if (!chartData || chartData.length === 0) 
      return { max: 0, min: 0, avg: 0, delta: 0, pct: 0, hasData: false };
    
    const prices = chartData.map(d => d.price);
    const firstPrice = prices[0];           // 기간 첫날 가격
    const lastPrice = prices[prices.length - 1];  // 기간 마지막날 가격
    const max = Math.max(...prices);
    const min = Math.min(...prices);
    const avg = Math.round(prices.reduce((a,b)=>a+b,0)/prices.length);
    
    // 변동 = 마지막 가격 - 첫 가격
    const delta = lastPrice - firstPrice;
    const pct = firstPrice !== 0 ? ((lastPrice - firstPrice) / firstPrice * 100) : 0;
    
    return {
        max,
        min,
        avg,
        delta,
        pct,
        firstPrice,
        lastPrice,
        hasData: prices.length > 1
    };
  };

  const renderCard = (item) => {
    const chartData = item.chart && item.chart.length > 0 ? item.chart : [{value:0}];
    
    const values = chartData.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const padding = (maxValue - minValue) * 0.05;
    
    return (
    <div key={item.name} className="bg-[#1e1e1e] p-3 sm:p-5 rounded-2xl border border-[#333] flex flex-col h-40 sm:h-48 hover:border-blue-500/50 transition-all shadow-lg">
      <div className="text-gray-400 text-xs font-bold mb-1">{item.name}</div>
      <div className="text-lg sm:text-2xl font-bold mb-1">{item.current.toLocaleString(undefined, {maximumFractionDigits:2})}</div>
      <div className={`text-xs font-bold flex items-center mb-2 sm:mb-4 ${item.pct >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
        {item.pct >= 0 ? <TrendingUp size={14} className="mr-1"/> : <TrendingDown size={14} className="mr-1"/>}
        {Math.abs(item.pct).toFixed(2)}%
      </div>
      <div className="mt-auto h-10 sm:h-12 w-full opacity-50">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <YAxis domain={[minValue - padding, maxValue + padding]} hide={true} />
            <Line type="linear" dataKey="value" stroke={item.pct >= 0 ? "#ff5252" : "#00e676"} strokeWidth={1.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )};

  return (
    <div className="flex min-h-screen bg-[#0e1117] text-white font-sans">
      {/* 사이드바 - 모바일에서 숨김 */}
      <aside className="w-64 border-r border-[#333] p-6 hidden lg:block bg-[#262730]">
        <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><Settings size={20}/> 설정</h2>
        <button onClick={() => window.location.reload()} className="w-full py-2 bg-[#333] hover:bg-[#444] rounded mb-6 text-sm flex justify-center items-center gap-2 transition">
            <RefreshCcw size={16}/> 새로고침
        </button>
        <label className="block text-sm text-gray-400 mb-2">차트 기간</label>
        <select value={globalPeriod} onChange={(e) => setGlobalPeriod(e.target.value)} className="w-full bg-[#0e1117] border border-[#555] rounded p-2 text-sm outline-none focus:border-blue-500">
            {['5일', '1개월', '6개월', '1년'].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <div className="mt-10 pt-10 border-t border-[#444]">
            <p className="text-xs text-gray-500">Version 2.3.0 (Mobile)</p>
        </div>
      </aside>

      {/* 메인 컨텐츠 - 모바일 패딩 조정 */}
      <main className="flex-1 p-3 sm:p-6 lg:p-8 overflow-y-auto overflow-x-hidden">
        <header className="mb-4 sm:mb-8">
            <h1 className="text-xl sm:text-3xl font-bold mb-2">📊 Seondori.com</h1>
        </header>

        {/* ✅ 탭 순서 변경: RAM 시세가 맨 앞 */}
        <div className="flex gap-1 sm:gap-2 mb-4 sm:mb-6 border-b border-[#333] pb-1 overflow-x-auto scrollbar-hide">
            {[
              {id: 'ram', label: '💾 RAM 시세', shortLabel: '💾 RAM'},
              {id: 'tradingview', label: '🔍 Trading View', shortLabel: '🔍 차트'}, 
              {id: 'indices', label: '📈 주가지수', shortLabel: '📈 지수'}, 
              {id: 'forex', label: '💱 환율', shortLabel: '💱 환율'}, 
              {id: 'bonds', label: '💰 국채 금리', shortLabel: '💰 금리'}, 
              {id: 'admin', label: '⚙️ ADMIN', shortLabel: '⚙️'}
            ].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-2 sm:px-4 py-2 text-xs sm:text-sm font-medium whitespace-nowrap rounded-t-lg transition-colors ${activeTab === tab.id ? 'bg-[#1e1e1e] text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-white'}`}>
                    <span className="hidden sm:inline">{tab.label}</span>
                    <span className="sm:hidden">{tab.shortLabel}</span>
                </button>
            ))}
        </div>

        {loading && <div className="text-blue-400 mb-4 text-sm animate-pulse">데이터를 불러오는 중...</div>}

        {activeTab === 'tradingview' && (
            <div>
                <h3 className="text-lg sm:text-xl font-bold mb-4">💡 TradingView 실시간 차트</h3>
                <div id="tradingview_chart" className="h-[400px] sm:h-[600px]"></div>
            </div>
        )}

        {activeTab !== 'ram' && activeTab !== 'admin' && activeTab !== 'tradingview' && data.market && (
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
                {activeTab === 'indices' && [...(data.market.indices || []), ...(data.market.macro || [])].map(renderCard)}
                {activeTab === 'forex' && (data.market.forex || []).map(renderCard)}
                {activeTab === 'bonds' && (data.market.bonds || []).map(renderCard)}
            </div>
        )}

        {activeTab === 'ram' && data.ram && (
            <div className="space-y-4 sm:space-y-6">
                {/* 헤더 */}
                <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                    <h3 className="font-bold text-base sm:text-lg">시세 히스토리</h3>
                    <select value={ramPeriod} onChange={(e)=>setRamPeriod(e.target.value)} className="bg-[#0e1117] border border-[#555] rounded px-3 py-1 text-sm outline-none w-full sm:w-auto">
                        <option value="5">5일</option>
                        <option value="15">15일</option>
                        <option value="30">1개월</option>
                        <option value="365">1년</option>
                    </select>
                </div>

                <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-6">
                    {/* 카테고리 버튼 - 모바일 그리드 */}
                    <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 mb-4 sm:mb-6">
                        {sortCategories(Object.keys(data.ram)).map(cat => (
                            <button key={cat} onClick={() => {
                              setSelectedCategory(cat);
                              if (data.ram[cat] && data.ram[cat].length > 0) {
                                setSelectedProduct(data.ram[cat][0].product);
                              }
                            }} className={`px-2 sm:px-3 py-1.5 text-xs rounded border transition text-center ${selectedCategory === cat ? 'bg-purple-600 border-purple-600 text-white' : 'bg-[#262730] border-[#444] text-gray-300 hover:bg-[#333]'}`}>
                                <span className="block sm:inline">{cat.replace(' RAM ', '\n').replace('(', '\n(')}</span>
                                <span className="text-xs ml-1 text-gray-400">({data.ram[cat]?.length || 0})</span>
                            </button>
                        ))}
                    </div>

                    {/* 제품 테이블 */}
                    {selectedCategory && data.ram[selectedCategory] ? (
                      <div className="overflow-x-auto max-h-48 sm:max-h-60 overflow-y-auto mb-4 sm:mb-8 border border-[#333] rounded-lg">
                        <table className="w-full text-left text-xs sm:text-sm">
                            <thead className="bg-[#262730] text-gray-400 sticky top-0">
                                <tr>
                                  <th className="py-2 px-2 sm:px-4">제품명</th>
                                  <th className="py-2 px-2 sm:px-4 text-right">가격</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.ram[selectedCategory]?.filter(item => item.product.toLowerCase().includes(ramSearch.toLowerCase())).map((item, i) => (
                                    <tr key={i} onClick={() => setSelectedProduct(item.product)} className={`cursor-pointer border-b border-[#333] transition ${selectedProduct === item.product ? 'bg-blue-500/20' : 'hover:bg-[#262730]'}`}>
                                        <td className="py-2 px-2 sm:px-4 text-xs sm:text-sm">{item.product}</td>
                                        <td className="py-2 px-2 sm:px-4 text-right font-mono text-purple-400 font-bold text-xs sm:text-sm">{item.price_formatted}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-gray-500 text-sm py-4">선택된 카테고리에 데이터가 없습니다.</div>
                    )}

                    {/* 제품 상세 차트 */}
                    {selectedProduct && (
                        <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333]">
                            {(() => {
                                const chartData = getRamTrend(selectedCategory, selectedProduct);
                                const stats = getStats(chartData);
                                return (
                                    <>
                                        {/* 제품명 & 변동 - 모바일 세로 배치 */}
                                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                                            <div>
                                              <div className="text-xs sm:text-sm text-gray-400 mb-1">제품</div>
                                              <div className="text-sm sm:text-xl font-bold leading-tight">{selectedProduct}</div>
                                            </div>
                                            <div className="text-left sm:text-right">
                                              <div className="text-xs text-gray-500 mb-1">
                                                {ramPeriod}일 변동 (첫날 → 오늘)
                                              </div>
                                              <div className={`text-base sm:text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
                                                {stats.delta > 0 ? '+' : ''}{stats.delta !== 0 ? stats.delta.toLocaleString() : '0'}원 
                                                <span className="text-sm">({stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%)</span>
                                              </div>
                                              {stats.hasData && (
                                                <div className="text-xs text-gray-500 mt-1">
                                                  {stats.firstPrice?.toLocaleString()}원 → {stats.lastPrice?.toLocaleString()}원
                                                </div>
                                              )}
                                            </div>
                                        </div>

                                        {/* 통계 카드 - 모바일 3열 */}
                                        <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-8">
                                            <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                              <div className="text-xs text-gray-500">최고가</div>
                                              <div className="font-bold text-sm sm:text-lg">{stats.max !== 0 ? stats.max.toLocaleString() : '-'}<span className="text-xs">원</span></div>
                                            </div>
                                            <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                              <div className="text-xs text-gray-500">최저가</div>
                                              <div className="font-bold text-sm sm:text-lg">{stats.min !== 0 ? stats.min.toLocaleString() : '-'}<span className="text-xs">원</span></div>
                                            </div>
                                            <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                              <div className="text-xs text-gray-500">평균가</div>
                                              <div className="font-bold text-sm sm:text-lg">{stats.avg !== 0 ? stats.avg.toLocaleString() : '-'}<span className="text-xs">원</span></div>
                                            </div>
                                        </div>

                                        {/* 차트 - 모바일 높이 조정 */}
                                        {chartData.length > 0 ? (
                                          <div className="h-48 sm:h-64 w-full">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                                    <XAxis 
                                                      dataKey="name" 
                                                      stroke="#666" 
                                                      tick={{fontSize: 10}} 
                                                      interval="preserveStartEnd"
                                                      tickMargin={8}
                                                    />
                                                    <YAxis 
                                                      domain={['auto', 'auto']} 
                                                      stroke="#666" 
                                                      tick={{fontSize: 10}} 
                                                      tickFormatter={(val) => `${(val/1000).toFixed(0)}k`}
                                                      width={40}
                                                    />
                                                    <Tooltip 
                                                      contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444', fontSize: '12px'}} 
                                                      formatter={(val) => [`${val.toLocaleString()}원`, '가격']} 
                                                    />
                                                    <Line type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} dot={{r: 3, fill: '#3b82f6'}} />
                                                </LineChart>
                                            </ResponsiveContainer>
                                          </div>
                                        ) : (
                                          <div className="h-48 sm:h-64 flex items-center justify-center text-gray-500 border border-[#333] rounded text-sm">
                                            아직 가격 히스토리 데이터가 없습니다.
                                          </div>
                                        )}
                                    </>
                                )
                            })()}
                        </div>
                    )}
                </div>
            </div>
        )}

        {activeTab === 'admin' && (
            <div className="max-w-2xl mx-auto animate-in fade-in">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4 sm:mb-6">
                    <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2"><Save size={24} className="text-red-500"/> 데이터 업데이트</h2>
                    <button onClick={handleDownload} className="flex items-center gap-2 px-4 py-2 bg-[#262730] hover:bg-[#333] rounded text-sm transition"><Download size={16}/> 백업 다운로드</button>
                </div>
                <div className="bg-[#1e1e1e] p-4 sm:p-6 rounded-2xl border border-[#333]">
                    <div className="grid grid-cols-2 gap-3 sm:gap-4 mb-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">날짜</label>
                            <input type="date" value={adminDate} onChange={(e)=>setAdminDate(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-2 sm:p-3 outline-none text-sm" />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-2">시간</label>
                            <select value={adminTime} onChange={(e)=>setAdminTime(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-2 sm:p-3 outline-none text-sm">
                                <option value="10:00">10:00 (오전)</option>
                                <option value="13:00">13:00 (점심)</option>
                                <option value="18:00">18:00 (오후)</option>
                            </select>
                        </div>
                    </div>
                    <div className="mb-4 sm:mb-6">
                        <label className="block text-sm text-gray-400 mb-2">텍스트 붙여넣기 (네이버 카페 글)</label>
                        <textarea value={adminText} onChange={(e)=>setAdminText(e.target.value)} className="w-full h-48 sm:h-64 bg-[#0b0e11] border border-[#555] rounded p-3 text-sm resize-none outline-none font-mono" placeholder="여기에 가격 정보를 포함한 전체 텍스트를 붙여넣으세요..."></textarea>
                    </div>
                    <button onClick={handleUpdate} className="w-full py-3 sm:py-4 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold transition">저장하기</button>
                    
                    {parseLog && (
                      <div className="mt-4 p-3 bg-[#0b0e11] border border-green-500/30 rounded text-sm text-green-400">
                        {parseLog}
                      </div>
                    )}
                </div>
            </div>
        )}
      </main>
    </div>
  );
};

export default App;
