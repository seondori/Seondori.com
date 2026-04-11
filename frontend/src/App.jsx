import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip, AreaChart, Area, CartesianGrid 
} from 'recharts';
import { Globe, Cpu, TrendingUp, TrendingDown, RefreshCcw, LayoutDashboard, Settings, Search, Save, Download, ShoppingCart } from 'lucide-react';

const App = () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [data, setData] = useState({ market: {}, ram: {}, history: {} });
  const [activeTab, setActiveTab] = useState('compuzone');  // ✅ 컴퓨존이 기본 탭
  const [loading, setLoading] = useState(false);
  
  const [globalPeriod, setGlobalPeriod] = useState('1개월');
  const [ramPeriod, setRamPeriod] = useState('30'); 

  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProduct, setSelectedProduct] = useState("");
  const [ramSearch, setRamSearch] = useState("");

  // DRAMeXchange states
  const [dramData, setDramData] = useState({ current_data: {}, price_history: {} });
  const [selectedDramType, setSelectedDramType] = useState('DDR5');
  const [selectedDramProduct, setSelectedDramProduct] = useState('');
  const [dramPeriod, setDramPeriod] = useState('30');

  // ✅ 신품 최저가 states
  const [newPriceData, setNewPriceData] = useState({ current: {}, history: {} });
  const [newSelectedCategory, setNewSelectedCategory] = useState("");
  const [newSelectedProduct, setNewSelectedProduct] = useState("");
  const [newPricePeriod, setNewPricePeriod] = useState('30');

  // ✅ 컴퓨존 states
  const [compuzoneData, setCompuzoneData] = useState({ products: {}, price_history: {}, last_updated: "" });
  const [czSelectedCategory, setCzSelectedCategory] = useState("");
  const [czSelectedCapacity, setCzSelectedCapacity] = useState("");
  const [czPeriod, setCzPeriod] = useState('30');

  const [adminDate, setAdminDate] = useState(new Date().toISOString().slice(0, 10));
  const [adminTime, setAdminTime] = useState("10:00");
  const [adminText, setAdminText] = useState("");
  const [parseLog, setParseLog] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [marketRes, ramRes, dramRes, newPriceRes, czRes] = await Promise.all([
        axios.get(`${API_URL}/api/market-data?period=${globalPeriod}`),
        axios.get(`${API_URL}/api/ram-data`),
        axios.get(`${API_URL}/api/dramexchange-data`),
        axios.get(`${API_URL}/api/ram-new-data`).catch(() => ({ data: { current: {}, trends: {} } })),
        axios.get(`${API_URL}/api/compuzone-data`).catch(() => ({ data: { products: {}, price_history: {}, last_updated: "" } }))
      ]);
      
      setData({
        market: marketRes.data,
        ram: ramRes.data.current || {},
        history: ramRes.data.trends || {}
      });

      setDramData(dramRes.data);
      
      if (dramRes.data.current_data && Object.keys(dramRes.data.current_data).length > 0) {
        const firstType = Object.keys(dramRes.data.current_data)[0];
        setSelectedDramType(firstType);
        const firstProduct = dramRes.data.current_data[firstType]?.[0]?.product;
        if (firstProduct) setSelectedDramProduct(firstProduct);
      }
      
      // 신품 최저가
      const newCurrent = newPriceRes.data.current || {};
      const newHistory = newPriceRes.data.trends || {};
      setNewPriceData({ current: newCurrent, history: newHistory });
      
      if (Object.keys(newCurrent).length > 0) {
        const sortedCats = sortCategories(Object.keys(newCurrent));
        const firstCat = sortedCats[0];
        if (firstCat) {
          setNewSelectedCategory(firstCat);
          const firstProd = newCurrent[firstCat]?.[0]?.product;
          if (firstProd) setNewSelectedProduct(firstProd);
        }
      }

      // ✅ 컴퓨존
      const czData = czRes.data || { products: {}, price_history: {}, last_updated: "" };
      setCompuzoneData(czData);
      
      if (czData.products && Object.keys(czData.products).length > 0) {
        const firstCat = Object.keys(czData.products)[0];
        setCzSelectedCategory(firstCat);
        const firstOpt = czData.products[firstCat]?.options?.[0]?.capacity;
        if (firstOpt) setCzSelectedCapacity(firstOpt);
      }

      if (ramRes.data.current) {
        const availableCats = Object.keys(ramRes.data.current);
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

  const getRamTrend = (category, productName, historySource = null) => {
    const history = historySource || data.history;
    if (!history) return [];
    
    const productTrend = history[productName];
    if (!productTrend || !Array.isArray(productTrend)) return [];
    
    const periodDays = historySource ? parseInt(newPricePeriod) : parseInt(ramPeriod);
    const slicedData = productTrend.slice(-periodDays);
    
    return slicedData.map(item => ({
      name: item.date.length > 10 ? item.date.substring(5, 16) : item.date.substring(5),
      price: item.price
    }));
  };

  const getStats = (chartData) => {
    if (!chartData || chartData.length === 0) 
      return { max: 0, min: 0, avg: 0, delta: 0, pct: 0, hasData: false };
    
    const prices = chartData.map(d => d.price);
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const max = Math.max(...prices);
    const min = Math.min(...prices);
    const avg = Math.round(prices.reduce((a,b)=>a+b,0)/prices.length);
    
    const delta = lastPrice - firstPrice;
    const pct = firstPrice !== 0 ? ((lastPrice - firstPrice) / firstPrice * 100) : 0;
    
    return { max, min, avg, delta, pct, firstPrice, lastPrice, hasData: prices.length > 1 };
  };

  // ============================================
  // ✅ 컴퓨존 히스토리 차트 데이터
  // ============================================
  const getCompuzoneTrend = (category, capacity) => {
  const history = compuzoneData.price_history || {};
  const timestamps = Object.keys(history).sort();
  const periodDays = parseInt(czPeriod);

  // 하루 3개 슬롯만 필터링 (10:xx, 13:xx, 18:xx 중 가장 가까운 것)
  const slots = ['10:00', '13:00', '18:00'];
  const dailyMap = {};

  timestamps.forEach(ts => {
    const [date, time] = ts.split(' ');
    if (!date || !time) return;
    const hour = parseInt(time.split(':')[0]);

    // 가장 가까운 슬롯 결정
    let slot;
    if (hour < 12) slot = '10:00';
    else if (hour < 16) slot = '13:00';
    else slot = '18:00';

    const key = `${date} ${slot}`;
    // 같은 슬롯이면 가장 나중 데이터로 덮어쓰기
    dailyMap[key] = ts;
  });

  const filtered = Object.values(dailyMap).sort();
  const recent = filtered.slice(-periodDays * 3);

  return recent.map(ts => {
    const dayData = history[ts]?.[category];
    if (!dayData) return null;
    const opt = dayData.find(o => o.capacity === capacity);
    if (!opt) return null;
    return {
      name: ts.split(' ')[0]?.substring(5) || ts.substring(5, 10),
      price: opt.price
    };
  }).filter(Boolean);
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

  // ============================================
  // ✅ 재사용 가능한 RAM 시세 탭 렌더러
  // ============================================
  const renderRamTab = ({ 
    currentData, historyData, 
    category, setCategory, 
    product, setProduct, 
    period, setPeriod, 
    colorAccent = '#3b82f6',
    title = '시세 히스토리',
    showSource = false 
  }) => (
    <div className="space-y-4 sm:space-y-6">
      <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
        <h3 className="font-bold text-base sm:text-lg">{title}</h3>
        <select value={period} onChange={(e) => setPeriod(e.target.value)} className="bg-[#0e1117] border border-[#555] rounded px-3 py-1 text-sm outline-none w-full sm:w-auto">
          <option value="5">5일</option>
          <option value="15">15일</option>
          <option value="30">1개월</option>
          <option value="365">1년</option>
        </select>
      </div>

      <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-6">
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 mb-4 sm:mb-6">
          {sortCategories(Object.keys(currentData)).map(cat => (
            <button key={cat} onClick={() => {
              setCategory(cat);
              if (currentData[cat] && currentData[cat].length > 0) {
                setProduct(currentData[cat][0].product);
              }
            }} className={`px-2 sm:px-3 py-1.5 text-xs rounded border transition text-center ${category === cat ? 'bg-purple-600 border-purple-600 text-white' : 'bg-[#262730] border-[#444] text-gray-300 hover:bg-[#333]'}`}>
              <span className="block sm:inline">{cat.replace(' RAM ', '\n').replace('(', '\n(')}</span>
              <span className="text-xs ml-1 text-gray-400">({currentData[cat]?.length || 0})</span>
            </button>
          ))}
        </div>

        {category && currentData[category] ? (
          <div className="overflow-x-auto max-h-48 sm:max-h-60 overflow-y-auto mb-4 sm:mb-8 border border-[#333] rounded-lg">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-[#262730] text-gray-400 sticky top-0">
                <tr>
                  <th className="py-2 px-2 sm:px-4">제품명</th>
                  <th className="py-2 px-2 sm:px-4 text-right">가격</th>
                  {showSource && <th className="py-2 px-2 sm:px-4 text-right hidden sm:table-cell">출처</th>}
                </tr>
              </thead>
              <tbody>
                {currentData[category]?.map((item, i) => (
                  <tr key={i} onClick={() => setProduct(item.product)} className={`cursor-pointer border-b border-[#333] transition ${product === item.product ? 'bg-blue-500/20' : 'hover:bg-[#262730]'}`}>
                    <td className="py-2 px-2 sm:px-4 text-xs sm:text-sm">
                      {item.product}
                      {showSource && item.source && <span className="block sm:hidden text-xs text-gray-500 mt-0.5">{item.source}</span>}
                    </td>
                    <td className="py-2 px-2 sm:px-4 text-right font-mono text-purple-400 font-bold text-xs sm:text-sm">
                      {item.price_formatted}
                      {showSource && item.link && <a href={item.link} target="_blank" rel="noopener noreferrer" className="block text-xs text-blue-400 hover:underline mt-0.5">바로가기 →</a>}
                    </td>
                    {showSource && <td className="py-2 px-2 sm:px-4 text-right text-xs text-gray-500 hidden sm:table-cell">{item.source || '-'}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-gray-500 text-sm py-4">선택된 카테고리에 데이터가 없습니다.</div>
        )}

        {product && (
          <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333]">
            {(() => {
              const chartData = getRamTrend(category, product, historyData);
              const stats = getStats(chartData);
              return (
                <>
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                    <div>
                      <div className="text-xs sm:text-sm text-gray-400 mb-1">제품</div>
                      <div className="text-sm sm:text-xl font-bold leading-tight">{product}</div>
                    </div>
                    <div className="text-left sm:text-right">
                      <div className="text-xs text-gray-500 mb-1">{period}일 변동 (첫날 → 오늘)</div>
                      <div className={`text-base sm:text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
                        {stats.delta > 0 ? '+' : ''}{stats.delta !== 0 ? stats.delta.toLocaleString() : '0'}원 
                        <span className="text-sm">({stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%)</span>
                      </div>
                      {stats.hasData && <div className="text-xs text-gray-500 mt-1">{stats.firstPrice?.toLocaleString()}원 → {stats.lastPrice?.toLocaleString()}원</div>}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-8">
                    {[{label:'최고가',val:stats.max},{label:'최저가',val:stats.min},{label:'평균가',val:stats.avg}].map(s => (
                      <div key={s.label} className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                        <div className="text-xs text-gray-500">{s.label}</div>
                        <div className="font-bold text-sm sm:text-lg">{s.val !== 0 ? s.val.toLocaleString() : '-'}<span className="text-xs">원</span></div>
                      </div>
                    ))}
                  </div>
                  {chartData.length > 0 ? (
                    <div className="h-48 sm:h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                          <XAxis dataKey="name" stroke="#666" tick={{fontSize: 10}} interval="preserveStartEnd" tickMargin={8} />
                          <YAxis domain={['auto', 'auto']} stroke="#666" tick={{fontSize: 10}} tickFormatter={(val) => `${(val/1000).toFixed(0)}k`} width={40} />
                          <Tooltip contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444', fontSize: '12px'}} formatter={(val) => [`${val.toLocaleString()}원`, '가격']} />
                          <Line type="monotone" dataKey="price" stroke={colorAccent} strokeWidth={2} dot={{r: 3, fill: colorAccent}} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-48 sm:h-64 flex items-center justify-center text-gray-500 border border-[#333] rounded text-sm">아직 가격 히스토리 데이터가 없습니다.</div>
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-[#0e1117] text-white font-sans">
      {/* 사이드바 */}
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
            <p className="text-xs text-gray-500">Version 2.5.0</p>
        </div>
      </aside>

      {/* 메인 컨텐츠 */}
      <main className="flex-1 p-3 sm:p-6 lg:p-8 overflow-y-auto overflow-x-hidden">
        <header className="mb-4 sm:mb-8">
            <h1 className="text-xl sm:text-3xl font-bold mb-2">📊 Seondori.com</h1>
        </header>

        {/* ✅ 탭 - 컴퓨존이 맨 앞 */}
        <div className="flex gap-1 sm:gap-2 mb-4 sm:mb-6 border-b border-[#333] pb-1 overflow-x-auto scrollbar-hide">
            {[
              {id: 'compuzone', label: '🛒 RAM 컴퓨존', shortLabel: '🛒 컴퓨존'},
              {id: 'ram', label: '💾 RAM 중고 매입시세', shortLabel: '💾 중고'},
              {id: 'ram-new', label: '🏷️ RAM 다나와', shortLabel: '🏷️ 다나와'},
              {id: 'dramexchange', label: '📊 DRAMeXchange', shortLabel: '📊 미국시세'},
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

        {/* ✅ 컴퓨존 탭 */}
        {activeTab === 'compuzone' && (
          <div className="space-y-4 sm:space-y-6">
            {/* 헤더 */}
            <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
              <div>
                <h3 className="font-bold text-base sm:text-lg flex items-center gap-2">
                  <ShoppingCart size={18} className="text-orange-400" />
                  컴퓨존 RAM 가격
                </h3>
                {compuzoneData.last_updated && (
                  <p className="text-xs text-gray-500 mt-1">마지막 업데이트: {compuzoneData.last_updated}</p>
                )}
              </div>
              <select value={czPeriod} onChange={(e) => setCzPeriod(e.target.value)} className="bg-[#0e1117] border border-[#555] rounded px-3 py-1 text-sm outline-none w-full sm:w-auto">
                <option value="7">7일</option>
                <option value="14">14일</option>
                <option value="30">1개월</option>
                <option value="90">3개월</option>
              </select>
            </div>

            {/* 제품 카테고리 선택 */}
            {Object.keys(compuzoneData.products).length > 0 ? (
              <>
                <div className="flex flex-col sm:flex-row gap-3">
                  {Object.entries(compuzoneData.products).map(([cat, productInfo]) => (
                    <button 
                      key={cat} 
                      onClick={() => {
                        setCzSelectedCategory(cat);
                        const firstOpt = productInfo.options?.[0]?.capacity;
                        if (firstOpt) setCzSelectedCapacity(firstOpt);
                      }}
                      className={`flex-1 p-3 sm:p-4 rounded-xl border transition text-left ${
                        czSelectedCategory === cat 
                          ? 'bg-orange-500/20 border-orange-500 text-orange-300' 
                          : 'bg-[#1e1e1e] border-[#333] hover:border-[#555] text-gray-300'
                      }`}
                    >
                      <div className="font-bold text-sm sm:text-base mb-1">{cat}</div>
                      <div className="text-xs text-gray-500">{productInfo.product_name}</div>
                      <div className="text-xs text-gray-600 mt-1">{productInfo.options?.length || 0}개 용량</div>
                    </button>
                  ))}
                </div>

                {/* 선택된 제품의 가격표 */}
                {czSelectedCategory && compuzoneData.products[czSelectedCategory] && (
                  <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-3 sm:p-6">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-2">
                      <div>
                        <h4 className="font-bold text-sm sm:text-lg">{compuzoneData.products[czSelectedCategory].product_name}</h4>
                        {compuzoneData.products[czSelectedCategory].source_url && (
                          <a 
                            href={compuzoneData.products[czSelectedCategory].source_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="text-xs text-blue-400 hover:underline mt-1 inline-block"
                          >
                            컴퓨존에서 보기 →
                          </a>
                        )}
                      </div>
                    </div>

                    {/* 용량별 가격 카드 */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mb-6">
                      {compuzoneData.products[czSelectedCategory].options?.map((opt) => (
                        <button
                          key={opt.capacity}
                          onClick={() => setCzSelectedCapacity(opt.capacity)}
                          className={`p-3 sm:p-4 rounded-xl border transition text-center ${
                            czSelectedCapacity === opt.capacity 
                              ? 'bg-orange-500/20 border-orange-500' 
                              : 'bg-[#0e1117] border-[#333] hover:border-[#555]'
                          }`}
                        >
                          <div className="text-lg sm:text-xl font-bold text-orange-400 mb-1">{opt.capacity}</div>
                          <div className="text-sm sm:text-base font-mono font-bold">{opt.price_formatted}</div>
                        </button>
                      ))}
                    </div>

                    {/* 선택된 용량의 가격 추이 차트 */}
                    {czSelectedCapacity && (
                      <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333]">
                        {(() => {
                          const chartData = getCompuzoneTrend(czSelectedCategory, czSelectedCapacity);
                          const stats = getStats(chartData);

                          return (
                            <>
                              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                                <div>
                                  <div className="text-xs text-gray-400 mb-1">용량</div>
                                  <div className="text-sm sm:text-xl font-bold">
                                    {compuzoneData.products[czSelectedCategory]?.product_name} — {czSelectedCapacity}
                                  </div>
                                </div>
                                <div className="text-left sm:text-right">
                                  <div className="text-xs text-gray-500 mb-1">{czPeriod}일 변동</div>
                                  <div className={`text-base sm:text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
                                    {stats.delta > 0 ? '+' : ''}{stats.delta !== 0 ? stats.delta.toLocaleString() : '0'}원
                                    <span className="text-sm"> ({stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%)</span>
                                  </div>
                                  {stats.hasData && (
                                    <div className="text-xs text-gray-500 mt-1">
                                      {stats.firstPrice?.toLocaleString()}원 → {stats.lastPrice?.toLocaleString()}원
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-8">
                                {[{label:'최고가',val:stats.max},{label:'최저가',val:stats.min},{label:'평균가',val:stats.avg}].map(s => (
                                  <div key={s.label} className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                    <div className="text-xs text-gray-500">{s.label}</div>
                                    <div className="font-bold text-sm sm:text-lg">{s.val !== 0 ? s.val.toLocaleString() : '-'}<span className="text-xs">원</span></div>
                                  </div>
                                ))}
                              </div>

                              {chartData.length > 0 ? (
                                <div className="h-48 sm:h-64 w-full">
                                  <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                                      <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                      <XAxis dataKey="name" stroke="#666" tick={{fontSize: 10}} interval="preserveStartEnd" tickMargin={8} />
                                      <YAxis domain={['auto', 'auto']} stroke="#666" tick={{fontSize: 10}} tickFormatter={(val) => `${(val/1000).toFixed(0)}k`} width={45} />
                                      <Tooltip contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444', fontSize: '12px'}} formatter={(val) => [`${val.toLocaleString()}원`, '가격']} />
                                      <Line type="monotone" dataKey="price" stroke="#f97316" strokeWidth={2} dot={{r: 3, fill: '#f97316'}} />
                                    </LineChart>
                                  </ResponsiveContainer>
                                </div>
                              ) : (
                                <div className="h-48 sm:h-64 flex items-center justify-center text-gray-500 border border-[#333] rounded text-sm">
                                  아직 가격 히스토리 데이터가 없습니다. 크롤러 실행 후 데이터가 쌓이면 차트가 표시됩니다.
                                </div>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="bg-[#1e1e1e] border border-[#333] rounded-lg p-8 text-center">
                <ShoppingCart size={48} className="mx-auto text-gray-600 mb-4" />
                <p className="text-gray-400 text-sm">컴퓨존 데이터가 아직 없습니다.</p>
                <p className="text-gray-600 text-xs mt-2">크롤러가 실행되면 여기에 가격이 표시됩니다.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'tradingview' && (
            <div>
                <h3 className="text-lg sm:text-xl font-bold mb-4">💡 TradingView 실시간 차트</h3>
                <div id="tradingview_chart" className="h-[400px] sm:h-[600px]"></div>
            </div>
        )}

        {['indices','forex','bonds'].includes(activeTab) && data.market && (
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
                {activeTab === 'indices' && [...(data.market.indices || []), ...(data.market.macro || [])].map(renderCard)}
                {activeTab === 'forex' && (data.market.forex || []).map(renderCard)}
                {activeTab === 'bonds' && (data.market.bonds || []).map(renderCard)}
            </div>
        )}

        {activeTab === 'ram' && data.ram && renderRamTab({
          currentData: data.ram,
          historyData: null,
          category: selectedCategory, setCategory: setSelectedCategory,
          product: selectedProduct, setProduct: setSelectedProduct,
          period: ramPeriod, setPeriod: setRamPeriod,
          colorAccent: '#3b82f6',
          title: '📦 중고 매입 시세 히스토리',
          showSource: false,
        })}

        {activeTab === 'ram-new' && renderRamTab({
          currentData: newPriceData.current,
          historyData: newPriceData.history,
          category: newSelectedCategory, setCategory: setNewSelectedCategory,
          product: newSelectedProduct, setProduct: setNewSelectedProduct,
          period: newPricePeriod, setPeriod: setNewPricePeriod,
          colorAccent: '#22c55e',
          title: '🏷️ RAM 신품 다나와 가격',
          showSource: true,
        })}

        {activeTab === 'dramexchange' && (
            <div className="max-w-7xl mx-auto animate-in fade-in">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                    <div>
                        <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
                            <TrendingUp size={24} className="text-purple-500"/> RAM-DRAMeXchange
                        </h2>
                        <p className="text-xs sm:text-sm text-gray-500 mt-1">글로벌 메모리 시세 추적</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <label className="text-xs text-gray-400">기간:</label>
                        <select value={dramPeriod} onChange={(e) => setDramPeriod(e.target.value)} className="bg-[#262730] border border-[#555] rounded px-2 sm:px-3 py-1 text-xs sm:text-sm outline-none">
                            <option value="7">7일</option>
                            <option value="14">14일</option>
                            <option value="30">30일</option>
                            <option value="90">90일</option>
                        </select>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div className="bg-[#1e1e1e] rounded-xl p-3 sm:p-4 border border-[#333]">
                        <h3 className="text-sm font-bold mb-3 text-gray-400">메모리 타입</h3>
                        <div className="flex flex-col gap-2">
                            {Object.keys(dramData.current_data).map(type => (
                                <button key={type} onClick={() => {
                                    setSelectedDramType(type);
                                    const firstProduct = dramData.current_data[type]?.[0]?.product;
                                    if (firstProduct) setSelectedDramProduct(firstProduct);
                                }} className={`text-left px-3 py-2 rounded text-xs sm:text-sm transition ${selectedDramType === type ? 'bg-purple-600 text-white font-bold' : 'bg-[#262730] hover:bg-[#333] text-gray-300'}`}>
                                    {type} ({dramData.current_data[type]?.length || 0})
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="bg-[#1e1e1e] rounded-xl p-3 sm:p-4 border border-[#333] lg:col-span-2">
                        <h3 className="text-sm font-bold mb-3 text-gray-400">제품 목록</h3>
                        {dramData.current_data[selectedDramType] && dramData.current_data[selectedDramType].length > 0 ? (
                            <div className="overflow-x-auto max-h-96 overflow-y-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-[#262730] text-gray-400 sticky top-0">
                                        <tr>
                                            <th className="py-2 px-2 sm:px-4 text-left">제품명</th>
                                            <th className="py-2 px-2 sm:px-4 text-right">Daily High</th>
                                            <th className="py-2 px-2 sm:px-4 text-right">Daily Low</th>
                                            <th className="py-2 px-2 sm:px-4 text-right">평균</th>
                                            <th className="py-2 px-2 sm:px-4 text-right">변동</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {dramData.current_data[selectedDramType].map((item, i) => (
                                            <tr key={i} onClick={() => setSelectedDramProduct(item.product)} className={`cursor-pointer border-b border-[#333] transition ${selectedDramProduct === item.product ? 'bg-purple-500/20' : 'hover:bg-[#262730]'}`}>
                                                <td className="py-2 px-2 sm:px-4 text-xs sm:text-sm">{item.product}</td>
                                                <td className="py-2 px-2 sm:px-4 text-right font-mono text-xs sm:text-sm">${item.daily_high}</td>
                                                <td className="py-2 px-2 sm:px-4 text-right font-mono text-xs sm:text-sm">${item.daily_low}</td>
                                                <td className="py-2 px-2 sm:px-4 text-right font-mono text-xs sm:text-sm">${item.session_average}</td>
                                                <td className={`py-2 px-2 sm:px-4 text-right font-mono text-xs sm:text-sm ${item.session_change.includes('+') ? 'text-red-400' : item.session_change.includes('-') ? 'text-green-400' : 'text-gray-400'}`}>
                                                    {item.session_change}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-gray-500 text-sm py-4">선택된 타입에 데이터가 없습니다.</div>
                        )}
                    </div>
                </div>

                {selectedDramProduct && (
                    <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333] mt-4">
                        {(() => {
                            const allHistory = dramData.price_history || {};
                            const timestamps = Object.keys(allHistory).sort();
                            const periodDays = parseInt(dramPeriod);
                            const recentTimestamps = timestamps.slice(-periodDays);
                            
                            const chartData = recentTimestamps.map(timestamp => {
                                const dayData = allHistory[timestamp];
                                const typeData = dayData[selectedDramType];
                                if (!typeData) return null;
                                const productData = typeData.find(p => p.product === selectedDramProduct);
                                if (!productData) return null;
                                return { name: timestamp.split(' ')[0].substring(5), price: productData.session_average || 0 };
                            }).filter(Boolean);

                            const prices = chartData.map(d => d.price).filter(p => p > 0);
                            const stats = {
                                max: prices.length > 0 ? Math.max(...prices) : 0,
                                min: prices.length > 0 ? Math.min(...prices) : 0,
                                avg: prices.length > 0 ? prices.reduce((a,b) => a+b, 0) / prices.length : 0,
                                delta: prices.length >= 2 ? prices[prices.length - 1] - prices[0] : 0,
                                pct: prices.length >= 2 ? ((prices[prices.length - 1] - prices[0]) / prices[0]) * 100 : 0,
                                firstPrice: prices[0] || 0, lastPrice: prices[prices.length - 1] || 0, hasData: prices.length > 0
                            };

                            return (
                                <>
                                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                                        <div>
                                            <div className="text-xs sm:text-sm text-gray-400 mb-1">제품</div>
                                            <div className="text-sm sm:text-xl font-bold leading-tight">{selectedDramProduct}</div>
                                        </div>
                                        <div className="text-left sm:text-right">
                                            <div className="text-xs text-gray-500 mb-1">{dramPeriod}일 변동 (첫날 → 오늘)</div>
                                            <div className={`text-base sm:text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
                                                {stats.delta > 0 ? '+' : ''}${stats.delta !== 0 ? stats.delta.toFixed(2) : '0'} 
                                                <span className="text-sm">({stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%)</span>
                                            </div>
                                            {stats.hasData && <div className="text-xs text-gray-500 mt-1">${stats.firstPrice.toFixed(2)} → ${stats.lastPrice.toFixed(2)}</div>}
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-8">
                                        {[{label:'최고가',val:stats.max},{label:'최저가',val:stats.min},{label:'평균가',val:stats.avg}].map(s => (
                                            <div key={s.label} className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                                <div className="text-xs text-gray-500">{s.label}</div>
                                                <div className="font-bold text-sm sm:text-lg">${s.val !== 0 ? s.val.toFixed(2) : '-'}</div>
                                            </div>
                                        ))}
                                    </div>
                                    {chartData.length > 0 ? (
                                        <div className="h-48 sm:h-64 w-full">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                                                    <XAxis dataKey="name" stroke="#666" tick={{fontSize: 10}} interval="preserveStartEnd" tickMargin={8} />
                                                    <YAxis domain={['auto', 'auto']} stroke="#666" tick={{fontSize: 10}} tickFormatter={(val) => `$${val.toFixed(1)}`} width={45} />
                                                    <Tooltip contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444', fontSize: '12px'}} formatter={(val) => [`$${val.toFixed(2)}`, '가격']} />
                                                    <Line type="monotone" dataKey="price" stroke="#a855f7" strokeWidth={2} dot={{r: 3, fill: '#a855f7'}} />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    ) : (
                                        <div className="h-48 sm:h-64 flex items-center justify-center text-gray-500 border border-[#333] rounded text-sm">아직 가격 히스토리 데이터가 없습니다.</div>
                                    )}
                                </>
                            );
                        })()}
                    </div>
                )}
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
                      <div className="mt-4 p-3 bg-[#0b0e11] border border-green-500/30 rounded text-sm text-green-400">{parseLog}</div>
                    )}
                </div>
            </div>
        )}
      </main>
    </div>
  );
};

export default App;
