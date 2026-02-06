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
    const chartData = item.chart && item.chart.length > 0 ? item.chart : [{value:0}];
    
    const values = chartData.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const padding = (maxValue - minValue) * 0.05;
    
    return (
    <div key={item.name} className="bg-[#1e1e1e] p-3 sm:p-5 rounded-2xl border border-[#333] flex flex-col h-40 sm:h-48 hover:border-blue-500/50 transition-all shadow-lg">
      <div className="text-gray-400 text-xs font-bold mb-1">{item.name}</div>
      <div className="text-lg sm:text-2xl font-bold mb-1">{item.current.toLocaleStrin
