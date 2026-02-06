import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip, AreaChart, Area, CartesianGrid 
} from 'recharts';
import { Globe, Cpu, TrendingUp, TrendingDown, RefreshCcw, LayoutDashboard, Settings, Search, Save, Download } from 'lucide-react';

const App = () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [data, setData] = useState({ market: {}, ram: {}, history: {}, dram: {}, dramHistory: {} });
  const [activeTab, setActiveTab] = useState('ram');  // ✅ RAM 시세가 기본 탭
  const [loading, setLoading] = useState(false);
  
  const [globalPeriod, setGlobalPeriod] = useState('1개월');
  const [ramPeriod, setRamPeriod] = useState('30'); 

  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProduct, setSelectedProduct] = useState("");
  const [ramSearch, setRamSearch] = useState("");

  // DRAM Exchange 선택 항목 추가
  const [selectedDramCategory, setSelectedDramCategory] = useState("");
  const [selectedDramProduct, setSelectedDramProduct] = useState("");

  const [adminDate, setAdminDate] = useState(new Date().toISOString().slice(0, 10));
  const [adminTime, setAdminTime] = useState("10:00");
  const [adminText, setAdminText] = useState("");
  const [parseLog, setParseLog] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [marketRes, ramRes, dramRes] = await Promise.all([
        axios.get(`${API_URL}/api/market-data?period=${globalPeriod}`),
        axios.get(`${API_URL}/api/ram-data`),
        axios.get(`${API_URL}/api/dram-exchange-data`)
      ]);
      
      console.log("RAM Data Response:", ramRes.data);
      console.log("DRAM Data Response:", dramRes.data);
      
      setData({
        market: marketRes.data,
        ram: ramRes.data.current || {},
        history: ramRes.data.trends || {},
        dram: dramRes.data.current || {},
        dramHistory: dramRes.data.trends || {}
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

      // DRAM Exchange 초기화
      if (dramRes.data.current) {
        const dramCats = Object.keys(dramRes.data.current);
        if (dramCats.length > 0) {
          setSelectedDramCategory(dramCats[0]);
          const firstDramProd = dramRes.data.current[dramCats[0]][0]?.product;
          if (firstDramProd) setSelectedDramProduct(firstDramProd);
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

    return slicedData.map((item, index) => ({
      name: item.date.split(' ')[0],  // "2026-02-06" 형태
      price: item.price,
      date: item.date
    }));
  };

  // DRAM Exchange 트렌드 데이터 추가
  const getDramTrend = (productName) => {
    if (!data.dramHistory) return [];
    
    const productTrend = data.dramHistory[productName];
    if (!productTrend || !Array.isArray(productTrend)) return [];
    
    const periodDays = parseInt(ramPeriod);
    const slicedData = productTrend.slice(-periodDays);

    return slicedData.map((item, index) => ({
      name: item.date.split(' ')[0],
      price: item.price,
      date: item.date
    }));
  };

  const getStats = (data) => {
    if (data.length === 0) return { max: 0, min: 0, avg: 0, delta: 0, pct: 0, hasData: false };
    
    const prices = data.map(d => d.price);
    const max = Math.max(...prices);
    const min = Math.min(...prices);
    const avg = Math.round(prices.reduce((a, b) => a + b, 0) / prices.length);
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const delta = lastPrice - firstPrice;
    const pct = firstPrice !== 0 ? ((delta / firstPrice) * 100) : 0;
    
    return { max, min, avg, delta, pct, hasData: true, firstPrice, lastPrice };
  };

  return (
    <div className="min-h-screen bg-[#0d1117]">
      {/* Header */}
      <header className="bg-[#161b22] border-b border-[#30363d]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl sm:text-2xl font-bold">Seondori Market Dashboard</h1>
          <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition"><RefreshCcw size={18}/> 새로고침</button>
        </div>
      </header>

      {/* Tabs */}
      <nav className="bg-[#161b22] border-b border-[#30363d] sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex gap-6 overflow-x-auto">
          <button onClick={() => setActiveTab('ram')} className={`py-3 font-bold border-b-2 transition ${activeTab === 'ram' ? 'border-blue-400 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-300'}`}>
            🇰🇷 RAM 시세
          </button>
          <button onClick={() => setActiveTab('dram')} className={`py-3 font-bold border-b-2 transition ${activeTab === 'dram' ? 'border-blue-400 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-300'}`}>
            🇺🇸 DRAM Exchange
          </button>
          <button onClick={() => setActiveTab('market')} className={`py-3 font-bold border-b-2 transition ${activeTab === 'market' ? 'border-blue-400 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-300'}`}>
            시장 지수
          </button>
          <button onClick={() => setActiveTab('tradingview')} className={`py-3 font-bold border-b-2 transition ${activeTab === 'tradingview' ? 'border-blue-400 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-300'}`}>
            USD/KRW
          </button>
          <button onClick={() => setActiveTab('admin')} className={`py-3 font-bold border-b-2 transition ${activeTab === 'admin' ? 'border-blue-400 text-blue-400' : 'border-transparent text-gray-400 hover:text-gray-300'}`}>
            💾 데이터 업데이트
          </button>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* RAM 시세 탭 */}
        {activeTab === 'ram' && (
            <div className="space-y-6">
                <div className="bg-blue-950 rounded-xl p-6 text-white">
                    <div className="flex items-center gap-2 mb-2">
                        <Cpu size={24}/>
                        <h2 className="text-2xl font-bold">한국 RAM 시세 (네이버 카페)</h2>
                    </div>
                    <p className="text-sm text-gray-300">단위: 원화 (KRW)</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">카테고리</label>
                        <select value={selectedCategory} onChange={(e) => {
                            setSelectedCategory(e.target.value);
                            const products = data.ram[e.target.value] || [];
                            if (products.length > 0) setSelectedProduct(products[0].product);
                        }} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            {Object.keys(data.ram).map(cat => (
                                <option key={cat} value={cat}>{cat}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">제품</label>
                        <select value={selectedProduct} onChange={(e) => setSelectedProduct(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            {(data.ram[selectedCategory] || []).map((prod, idx) => (
                                <option key={idx} value={prod.product}>{prod.product}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">기간</label>
                        <select value={ramPeriod} onChange={(e) => setRamPeriod(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            <option value="7">7일</option>
                            <option value="30">30일</option>
                            <option value="60">60일</option>
                            <option value="90">90일</option>
                        </select>
                    </div>
                </div>

                {/* RAM 검색 */}
                {selectedCategory && (
                    <div className="relative">
                        <Search className="absolute left-3 top-3 text-gray-500" size={18}/>
                        <input type="text" placeholder="제품 검색..." value={ramSearch} onChange={(e) => setRamSearch(e.target.value)} className="w-full pl-10 pr-4 py-2 bg-[#0b0e11] border border-[#555] rounded text-sm outline-none"/>
                    </div>
                )}

                {/* RAM 제품 테이블 */}
                {selectedCategory && data.ram[selectedCategory] && (
                    <div className="bg-[#0e1117] rounded-xl border border-[#333] overflow-hidden">
                      <div className="overflow-x-auto max-h-64 sm:max-h-none">
                        <table className="w-full">
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
                </div>

                {/* RAM 차트 */}
                {selectedProduct && (
                    <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333]">
                        {(() => {
                            const chartData = getRamTrend(selectedCategory, selectedProduct);
                            const stats = getStats(chartData);
                            return (
                                <>
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
        )}

        {/* DRAM Exchange 탭 추가 */}
        {activeTab === 'dram' && (
            <div className="space-y-6">
                <div className="bg-green-950 rounded-xl p-6 text-white">
                    <div className="flex items-center gap-2 mb-2">
                        <Globe size={24}/>
                        <h2 className="text-2xl font-bold">DRAM Exchange 시세</h2>
                    </div>
                    <p className="text-sm text-gray-300">단위: 미국 달러 (USD)</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">카테고리</label>
                        <select value={selectedDramCategory} onChange={(e) => {
                            setSelectedDramCategory(e.target.value);
                            const products = data.dram[e.target.value] || [];
                            if (products.length > 0) setSelectedDramProduct(products[0].product);
                        }} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            {Object.keys(data.dram).map(cat => (
                                <option key={cat} value={cat}>{cat}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">제품</label>
                        <select value={selectedDramProduct} onChange={(e) => setSelectedDramProduct(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            {(data.dram[selectedDramCategory] || []).map((prod, idx) => (
                                <option key={idx} value={prod.product}>{prod.product}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-2">기간</label>
                        <select value={ramPeriod} onChange={(e) => setRamPeriod(e.target.value)} className="w-full bg-[#0b0e11] border border-[#555] rounded p-3 outline-none text-sm">
                            <option value="7">7일</option>
                            <option value="30">30일</option>
                            <option value="60">60일</option>
                            <option value="90">90일</option>
                        </select>
                    </div>
                </div>

                {/* DRAM 차트 */}
                {selectedDramProduct && (
                    <div className="bg-[#0e1117] rounded-xl p-3 sm:p-6 border border-[#333]">
                        {(() => {
                            const chartData = getDramTrend(selectedDramProduct);
                            const stats = getStats(chartData);
                            return (
                                <>
                                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-4 sm:mb-6 gap-2">
                                        <div>
                                          <div className="text-xs sm:text-sm text-gray-400 mb-1">제품</div>
                                          <div className="text-sm sm:text-xl font-bold leading-tight">{selectedDramProduct}</div>
                                        </div>
                                        <div className="text-left sm:text-right">
                                          <div className="text-xs text-gray-500 mb-1">
                                            {ramPeriod}일 변동
                                          </div>
                                          <div className={`text-base sm:text-xl font-bold ${stats.delta >= 0 ? 'text-[#ff5252]' : 'text-[#00e676]'}`}>
                                            {stats.delta > 0 ? '+' : ''}{stats.delta.toFixed(2)}$ 
                                            <span className="text-sm">({stats.pct >= 0 ? '+' : ''}{stats.pct.toFixed(2)}%)</span>
                                          </div>
                                          {stats.hasData && (
                                            <div className="text-xs text-gray-500 mt-1">
                                              ${stats.firstPrice?.toFixed(2)} → ${stats.lastPrice?.toFixed(2)}
                                            </div>
                                          )}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-4 sm:mb-8">
                                        <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                          <div className="text-xs text-gray-500">최고가</div>
                                          <div className="font-bold text-sm sm:text-lg">${stats.max.toFixed(2)}</div>
                                        </div>
                                        <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                          <div className="text-xs text-gray-500">최저가</div>
                                          <div className="font-bold text-sm sm:text-lg">${stats.min.toFixed(2)}</div>
                                        </div>
                                        <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center">
                                          <div className="text-xs text-gray-500">평균가</div>
                                          <div className="font-bold text-sm sm:text-lg">${stats.avg.toFixed(2)}</div>
                                        </div>
                                    </div>

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
                                                  stroke="#666" 
                                                  tick={{fontSize: 10}}
                                                  width={40}
                                                />
                                                <Tooltip 
                                                  contentStyle={{backgroundColor: '#1e1e1e', border: '1px solid #444', fontSize: '12px'}} 
                                                  formatter={(val) => [`$${val.toFixed(2)}`, '가격']} 
                                                />
                                                <Line type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} dot={{r: 3, fill: '#10b981'}} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                      </div>
                                    ) : (
                                      <div className="h-48 sm:h-64 flex items-center justify-center text-gray-500 border border-[#333] rounded text-sm">
                                        아직 데이터가 없습니다.
                                      </div>
                                    )}
                                </>
                            )
                        })()}
                    </div>
                )}
            </div>
        )}

        {activeTab === 'market' && (
            <div className="text-center text-gray-500">
                시장 지수 탭 내용 (기존과 동일)
            </div>
        )}

        {activeTab === 'tradingview' && (
            <div id="tradingview_chart" style={{height: '600px'}} />
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
