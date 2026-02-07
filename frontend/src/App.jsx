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

  // DRAMeXchange states
  const [dramData, setDramData] = useState({ price_data: {}, price_history: {} });
  const [selectedDramType, setSelectedDramType] = useState('DDR5');
  const [selectedDramProduct, setSelectedDramProduct] = useState('');
  const [dramPeriod, setDramPeriod] = useState('30');

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
        axios.get(`${API_URL}/api/dramexchange-data`)
      ]);
      
      console.log("RAM Data Response:", ramRes.data);
      console.log("DRAM Exchange Data:", dramRes.data);
      
      setData({
        market: marketRes.data,
        ram: ramRes.data.current || {},
        history: ramRes.data.trends || {}
      });

      // Set DRAMeXchange data
      setDramData(dramRes.data);
      
      // Set initial DRAM product selection
      if (dramRes.data.price_data && Object.keys(dramRes.data.price_data).length > 0) {
        const firstType = Object.keys(dramRes.data.price_data)[0];
        setSelectedDramType(firstType);
        const firstProduct = dramRes.data.price_data[firstType]?.[0]?.product;
        if (firstProduct) setSelectedDramProduct(firstProduct);
      }
      
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
    // 램 데이터용 차트 데이터 생성
    const chartData = item.chart || getRamTrend(selectedCategory, item.name);
    
    // 통계 계산
    const stats = getStats(chartData);
    const isUp = stats.delta > 0;
    const isDown = stats.delta < 0;

    return (
    <div key={item.name} className="bg-[#1e1e1e] p-3 sm:p-5 rounded-2xl border border-[#333] flex flex-col h-40 sm:h-48 hover:border-blue-500/50 transition-all shadow-lg">
      <div className="text-gray-400 text-xs font-bold mb-1 truncate">{item.name}</div>
      <div className="text-lg sm:text-2xl font-bold mb-1 flex items-baseline gap-2">
        {item.current ? item.current.toLocaleString() : 0}원
        {stats.hasData && (
          <span className={`text-xs font-medium ${isUp ? 'text-red-400' : isDown ? 'text-blue-400' : 'text-gray-500'}`}>
            {isUp ? '▲' : isDown ? '▼' : '-'} {Math.abs(stats.delta).toLocaleString()}원 ({stats.pct.toFixed(1)}%)
          </span>
        )}
      </div>
      
      {/* 미니 차트 */}
      <div className="flex-1 w-full min-h-0 mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id={`grad_${item.name}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={isUp ? "#ef4444" : "#3b82f6"} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={isUp ? "#ef4444" : "#3b82f6"} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <Area 
              type="monotone" 
              dataKey="price" 
              stroke={isUp ? "#ef4444" : "#3b82f6"} 
              fill={`url(#grad_${item.name})`} 
              strokeWidth={2} 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
    );
  };

  // ============================================
  // 메인 렌더링
  // ============================================
  return (
    <div className="min-h-screen bg-[#121212] text-white font-sans selection:bg-blue-500/30">
      <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
        
        {/* 헤더 */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
          <div className="flex items-center gap-3">
            <Cpu className="w-8 h-8 text-blue-500" />
            <h1 className="text-2xl sm:text-3xl font-black bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Seondori Market
            </h1>
          </div>
          <div className="flex bg-[#1e1e1e] p-1 rounded-xl border border-[#333]">
            {[
              { id: 'ram', label: 'RAM 시세', icon: Cpu },
              { id: 'dram', label: 'DRAM 현물', icon: LayoutDashboard },
              { id: 'tradingview', label: '시장지표', icon: TrendingUp },
              { id: 'admin', label: '관리자', icon: Settings }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold transition-all ${
                  activeTab === tab.id 
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' 
                    : 'text-gray-400 hover:text-white hover:bg-[#333]'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ==================== 1. RAM 시세 탭 ==================== */}
        {activeTab === 'ram' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-[#1e1e1e] p-4 rounded-2xl border border-[#333]">
              <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-2 sm:pb-0">
                {data.ram && Object.keys(data.ram).length > 0 ? (
                  sortCategories(Object.keys(data.ram)).map(cat => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-4 py-2 rounded-xl text-sm font-bold whitespace-nowrap transition-all border ${
                        selectedCategory === cat
                          ? 'bg-blue-500/10 border-blue-500 text-blue-400'
                          : 'bg-[#252525] border-transparent text-gray-400 hover:border-[#444]'
                      }`}
                    >
                      {cat.split(' ')[0]}
                    </button>
                  ))
                ) : (
                  <div className="text-gray-500 text-sm">데이터 로딩중...</div>
                )}
              </div>
              <div className="flex items-center gap-2 bg-[#252525] px-3 py-2 rounded-xl w-full sm:w-auto">
                <Search className="w-4 h-4 text-gray-400" />
                <input 
                  type="text" 
                  placeholder="제품명 검색..." 
                  className="bg-transparent border-none focus:outline-none text-sm w-full"
                  value={ramSearch}
                  onChange={(e) => setRamSearch(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {loading ? (
                <div className="col-span-full text-center py-20 text-gray-500">데이터를 불러오는 중입니다...</div>
              ) : (
                selectedCategory && data.ram[selectedCategory] ? (
                  data.ram[selectedCategory]
                    .filter(item => item.product.toLowerCase().includes(ramSearch.toLowerCase()))
                    .map(item => renderCard({ 
                      name: item.product, 
                      current: item.price 
                    }))
                ) : (
                  <div className="col-span-full text-center py-20 text-gray-500">표시할 데이터가 없습니다.</div>
                )
              )}
            </div>
          </div>
        )}

        {/* ==================== 2. DRAM 현물 탭 ==================== */}
        {activeTab === 'dram' && (
          <div className="space-y-6">
            <div className="bg-[#1e1e1e] p-6 rounded-2xl border border-[#333]">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-green-400" />
                DRAM Exchange (Global Spot Price)
              </h2>
              
              {/* DRAM 컨트롤러 */}
              <div className="flex flex-wrap gap-4 mb-6">
                <select 
                  className="bg-[#252525] border border-[#444] rounded-lg px-4 py-2 text-sm"
                  value={selectedDramType}
                  onChange={(e) => {
                    setSelectedDramType(e.target.value);
                    // 타입 변경 시 첫 번째 제품 자동 선택
                    const products = dramData.price_data[e.target.value];
                    if (products && products.length > 0) {
                      setSelectedDramProduct(products[0].product);
                    }
                  }}
                >
                  {Object.keys(dramData.price_data || {}).map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>

                <select 
                  className="bg-[#252525] border border-[#444] rounded-lg px-4 py-2 text-sm max-w-xs truncate"
                  value={selectedDramProduct}
                  onChange={(e) => setSelectedDramProduct(e.target.value)}
                >
                  {(dramData.price_data?.[selectedDramType] || []).map(p => (
                    <option key={p.product} value={p.product}>{p.product}</option>
                  ))}
                </select>
              </div>

              {/* DRAM 테이블 */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-gray-400">
                  <thead className="bg-[#252525] text-gray-200 uppercase font-bold">
                    <tr>
                      <th className="px-4 py-3 rounded-tl-lg">Product</th>
                      <th className="px-4 py-3 text-right">High</th>
                      <th className="px-4 py-3 text-right">Low</th>
                      <th className="px-4 py-3 text-right">Avg</th>
                      <th className="px-4 py-3 text-right rounded-tr-lg">Change</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#333]">
                    {(dramData.price_data?.[selectedDramType] || []).map((item, idx) => (
                      <tr key={idx} className="hover:bg-[#252525] transition-colors">
                        <td className="px-4 py-3 font-medium text-white">{item.product}</td>
                        <td className="px-4 py-3 text-right">${item.daily_high}</td>
                        <td className="px-4 py-3 text-right">${item.daily_low}</td>
                        <td className="px-4 py-3 text-right font-bold text-blue-400">${item.session_average}</td>
                        <td className={`px-4 py-3 text-right ${
                          item.session_change.includes('+') ? 'text-red-400' : 
                          item.session_change.includes('-') ? 'text-blue-400' : 'text-gray-400'
                        }`}>
                          {item.session_change}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ==================== 3. 시장 지표 탭 ==================== */}
        {activeTab === 'tradingview' && (
          <div className="bg-[#1e1e1e] rounded-2xl border border-[#333] overflow-hidden h-[600px] w-full relative">
            <div id="tradingview_chart" className="w-full h-full" />
          </div>
        )}

        {/* ==================== 4. 관리자 탭 ==================== */}
        {activeTab === 'admin' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-[#1e1e1e] p-6 rounded-2xl border border-[#333]">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Settings className="w-5 h-5 text-gray-400" />
                관리자 데이터 입력
              </h2>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1">날짜</label>
                  <input 
                    type="date" 
                    value={adminDate}
                    onChange={(e) => setAdminDate(e.target.value)}
                    className="w-full bg-[#252525] border border-[#444] rounded-lg px-4 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 mb-1">시간</label>
                  <input 
                    type="time" 
                    value={adminTime}
                    onChange={(e) => setAdminTime(e.target.value)}
                    className="w-full bg-[#252525] border border-[#444] rounded-lg px-4 py-2 text-sm"
                  />
                </div>
              </div>

              <textarea 
                className="w-full h-64 bg-[#252525] border border-[#444] rounded-lg p-4 text-sm font-mono focus:border-blue-500 transition-colors mb-4"
                placeholder="여기에 원본 텍스트를 붙여넣으세요..."
                value={adminText}
                onChange={(e) => setAdminText(e.target.value)}
              />

              <div className="flex gap-3">
                <button 
                  onClick={handleUpdate}
                  className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-all"
                >
                  <Save className="w-4 h-4" />
                  데이터 파싱 및 저장
                </button>
                <button 
                  onClick={handleDownload}
                  className="px-4 bg-[#333] hover:bg-[#444] text-gray-300 rounded-lg flex items-center justify-center gap-2 transition-all"
                  title="백업 다운로드"
                >
                  <Download className="w-4 h-4" />
                </button>
              </div>

              {parseLog && (
                <div className="mt-4 p-3 bg-black/30 rounded-lg text-xs text-green-400 font-mono">
                  {parseLog}
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default App;
