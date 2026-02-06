import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LineChart, Line, ResponsiveContainer, YAxis, XAxis, Tooltip, AreaChart, Area, CartesianGrid, Legend
} from 'recharts';
import { Globe, Cpu, TrendingUp, TrendingDown, RefreshCcw, LayoutDashboard, Settings, Search, Save, Download, DollarSign } from 'lucide-react';

const App = () => {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  const [data, setData] = useState({ market: {}, ram: {}, dram: {}, history: {}, dramHistory: {} });
  const [activeTab, setActiveTab] = useState('ram');
  const [loading, setLoading] = useState(false);
  
  const [globalPeriod, setGlobalPeriod] = useState('1개월');
  const [ramPeriod, setRamPeriod] = useState('30'); 

  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedDramCategory, setSelectedDramCategory] = useState("");
  const [selectedDramProduct, setSelectedDramProduct] = useState("");
  const [ramSearch, setRamSearch] = useState("");

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
      console.log("DRAM Exchange Response:", dramRes.data);
      
      setData({
        market: marketRes.data,
        ram: ramRes.data.current || {},
        dram: dramRes.data.current || {},
        history: ramRes.data.trends || {},
        dramHistory: dramRes.data.trends || {}
      });
      
      // RAM 카테고리 설정
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

      // DRAM Exchange 카테고리 설정
      if (dramRes.data.current) {
        const dramCats = Object.keys(dramRes.data.current);
        const firstDramCat = dramCats[0];
        
        if (firstDramCat) {
            setSelectedDramCategory(firstDramCat);
            const firstDramProd = dramRes.data.current[firstDramCat][0]?.product;
            if (firstDramProd) setSelectedDramProduct(firstDramProd);
        }
      }
    } catch (err) { 
      console.error("Data fetch error:", err); 
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const sortCategories = (categories) => {
    const order = [
      "DDR5 RAM (데스크탑)",
      "DDR4 RAM (데스크탑)",
      "DDR3 RAM (데스크탑)",
      "DDR5 RAM (노트북)",
      "DDR4 RAM (노트북)",
      "DDR3 RAM (노트북)",
    ];
    return categories.sort((a, b) => {
      const indexA = order.indexOf(a);
      const indexB = order.indexOf(b);
      return (indexA === -1 ? 999 : indexA) - (indexB === -1 ? 999 : indexB);
    });
  };

  // RAM 시세 차트 데이터
  const getRamChartData = () => {
    if (!selectedProduct || !data.history[selectedProduct]) return [];
    const hist = data.history[selectedProduct] || [];
    return hist
      .slice(-parseInt(ramPeriod))
      .map(item => ({
        date: item.date,
        price: item.price,
        displayDate: item.date.split(' ')[0]
      }));
  };

  // DRAM Exchange 차트 데이터
  const getDramChartData = () => {
    if (!selectedDramProduct || !data.dramHistory[selectedDramProduct]) return [];
    const hist = data.dramHistory[selectedDramProduct] || [];
    return hist
      .slice(-parseInt(ramPeriod))
      .map(item => ({
        date: item.date,
        price: item.price,
        displayDate: item.date.split(' ')[0]
      }));
  };

  // ============================================
  // UI 렌더링
  // ============================================

  const renderRamTab = () => (
    <div className="space-y-6">
      {/* 상단 정보 */}
      <div className="bg-gradient-to-r from-blue-900 to-blue-800 rounded-lg p-6 text-white">
        <div className="flex items-center gap-3 mb-4">
          <Cpu size={28} />
          <div>
            <h2 className="text-2xl font-bold">한국 RAM 시세 (네이버 카페)</h2>
            <p className="text-blue-200">단위: 원화 (KRW)</p>
          </div>
        </div>
        <p className="text-sm text-blue-100">최근 {data.ram.total_days || 0}일간의 데이터 | {data.ram.date_range || '데이터 없음'}</p>
      </div>

      {/* 카테고리 선택 */}
      <div className="space-y-4">
        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">카테고리</span>
          <select 
            value={selectedCategory} 
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              const products = data.ram[e.target.value] || [];
              if (products.length > 0) setSelectedProduct(products[0].product);
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {Object.keys(data.ram).map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">제품</span>
          <select 
            value={selectedProduct} 
            onChange={(e) => setSelectedProduct(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {(data.ram[selectedCategory] || []).map((prod, idx) => (
              <option key={idx} value={prod.product}>{prod.product}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">기간</span>
          <select 
            value={ramPeriod} 
            onChange={(e) => setRamPeriod(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="7">7일</option>
            <option value="30">30일</option>
            <option value="60">60일</option>
            <option value="90">90일</option>
          </select>
        </label>
      </div>

      {/* 차트 */}
      <div className="bg-white rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-4">가격 추이</h3>
        {getRamChartData().length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={getRamChartData()}>
              <defs>
                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="displayDate" />
              <YAxis />
              <Tooltip formatter={(value) => `₩${value.toLocaleString()}`} />
              <Area type="monotone" dataKey="price" stroke="#3b82f6" fillOpacity={1} fill="url(#colorPrice)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500">데이터 없음</p>
        )}
      </div>

      {/* 현재 가격 */}
      {selectedProduct && data.ram[selectedCategory] && (
        <div className="bg-blue-50 rounded-lg p-4">
          <p className="text-gray-700"><strong>{selectedProduct}</strong></p>
          <p className="text-2xl font-bold text-blue-600">
            ₩{data.ram[selectedCategory].find(p => p.product === selectedProduct)?.price.toLocaleString() || 'N/A'}
          </p>
        </div>
      )}
    </div>
  );

  const renderDramExchangeTab = () => (
    <div className="space-y-6">
      {/* 상단 정보 */}
      <div className="bg-gradient-to-r from-green-900 to-green-800 rounded-lg p-6 text-white">
        <div className="flex items-center gap-3 mb-4">
          <DollarSign size={28} />
          <div>
            <h2 className="text-2xl font-bold">DRAM Exchange 시세</h2>
            <p className="text-green-200">단위: 미국 달러 (USD)</p>
          </div>
        </div>
        <p className="text-sm text-green-100">미국 기준 11:00, 14:40, 18:10 업데이트 | {data.dram.date_range || '데이터 없음'}</p>
      </div>

      {/* 카테고리 선택 */}
      <div className="space-y-4">
        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">카테고리</span>
          <select 
            value={selectedDramCategory} 
            onChange={(e) => {
              setSelectedDramCategory(e.target.value);
              const products = data.dram[e.target.value] || [];
              if (products.length > 0) setSelectedDramProduct(products[0].product);
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
          >
            {Object.keys(data.dram).map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">제품</span>
          <select 
            value={selectedDramProduct} 
            onChange={(e) => setSelectedDramProduct(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
          >
            {(data.dram[selectedDramCategory] || []).map((prod, idx) => (
              <option key={idx} value={prod.product}>{prod.product}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-semibold text-gray-700 mb-2 block">기간</span>
          <select 
            value={ramPeriod} 
            onChange={(e) => setRamPeriod(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500"
          >
            <option value="7">7일</option>
            <option value="30">30일</option>
            <option value="60">60일</option>
            <option value="90">90일</option>
          </select>
        </label>
      </div>

      {/* 차트 */}
      <div className="bg-white rounded-lg p-6 shadow">
        <h3 className="text-lg font-semibold mb-4">가격 추이 (USD)</h3>
        {getDramChartData().length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={getDramChartData()}>
              <defs>
                <linearGradient id="colorDramPrice" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="displayDate" />
              <YAxis />
              <Tooltip formatter={(value) => `$${value.toFixed(2)}`} />
              <Area type="monotone" dataKey="price" stroke="#10b981" fillOpacity={1} fill="url(#colorDramPrice)" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500">데이터 없음</p>
        )}
      </div>

      {/* 현재 가격 */}
      {selectedDramProduct && data.dram[selectedDramCategory] && (
        <div className="bg-green-50 rounded-lg p-4">
          <p className="text-gray-700"><strong>{selectedDramProduct}</strong></p>
          <p className="text-2xl font-bold text-green-600">
            ${data.dram[selectedDramCategory].find(p => p.product === selectedDramProduct)?.session_average?.toFixed(2) || 'N/A'}
          </p>
        </div>
      )}
    </div>
  );

  // 다른 탭들은 기존과 동일...
  
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* 헤더 */}
      <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Seondori Market Dashboard</h1>
          <button 
            onClick={fetchData}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <RefreshCcw size={18} /> 새로고침
          </button>
        </div>
      </header>

      {/* 탭 */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex gap-6 overflow-x-auto">
            {[
              { id: 'ram', label: '🇰🇷 RAM 시세', icon: Cpu },
              { id: 'dram', label: '🇺🇸 DRAM Exchange', icon: DollarSign },
              { id: 'market', label: '📊 시장 지수', icon: TrendingUp },
              { id: 'tradingview', label: '📈 USD/KRW', icon: Globe },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-4 font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* 콘텐츠 */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {activeTab === 'ram' && renderRamTab()}
        {activeTab === 'dram' && renderDramExchangeTab()}
        {/* 다른 탭 렌더링... */}
      </main>
    </div>
  );
};

export default App;
