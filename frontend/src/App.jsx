import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// ✅ StatCard 컴포넌트 분리 (공통 UI 재사용)
const StatCard = ({ label, value, currency, decimals = 0, isPositive = null }) => {
  const displayValue =
    value === null || value === undefined || isNaN(value) ? '-' :
    `${currency}${decimals > 0 ? value.toFixed(decimals) : value.toLocaleString()}` +
    (currency === '원' ? '원' : '');

  // 🟢🔴 색상 로직: null이면 중립(grey), otherwise change-color logic (optional)
  const colorClass = isPositive === true ? 'text-green-400' :
                   isPositive === false ? 'text-red-400' :
                   'text-gray-300';

  return (
    <div className="bg-[#1e1e1e] p-2 sm:p-3 rounded border border-[#333] text-center flex flex-col items-center justify-center">
      <div className="text-xs sm:text-sm text-gray-500 mb-1">{label}</div>
      <div className={`font-bold text-sm sm:text-lg ${colorClass}`}>
        {displayValue}
      </div>
    </div>
  );
};

export default function App() {
  const [activeTab, setActiveTab] = useState('cafe'); // 'cafe' | 'dramexchange'
  const [dramPeriod, setDramPeriod] = useState('6m'); // '1m' | '3m' | '6m' | '1y'
  const [selectedDramType, setSelectedDramType] = useState('DDR5');
  const [dramData, setDramData] = useState([]); // 예: [{date: '2024-01', DDR5: 12.5, DDR4: 8.2}, ...]
  const [chartData, setChartData] = useState([]);
  const [selectedDramProduct, setSelectedDramProduct] = useState(null);

  // Admin state
  const [adminText, setAdminText] = useState('');
  const [parseLog, setParseLog] = useState('');
  const [adminError, setAdminError] = useState('');

  // DRAMeXchange stats state
  const [stats, setStats] = useState({
    max: null,
    min: null,
    avg: null,
    current: null,
    maxDate: '',
    minDate: '',
  });

  // 🔄 DRAMeXchange Stats 계산 (useMemo로 최적화)
  const calculatedStats = useMemo(() => {
    if (chartData.length === 0) return { max: 0, min: 0, avg: 0, current: 0, maxDate: '-', minDate: '-' };
    const values = chartData.map(d => d[selectedDramType]);
    const validValues = values.filter(v => v !== null && !isNaN(v));
    if (validValues.length === 0) return { max: 0, min: 0, avg: 0, current: 0, maxDate: '-', minDate: '-' };
    
    const max = Math.max(...validValues);
    const min = Math.min(...validValues);
    const avg = validValues.reduce((a, b) => a + b, 0) / validValues.length;

    // Find dates
    const maxDate = chartData.find(d => d[selectedDramType] === max)?.date || '-';
    const minDate = chartData.find(d => d[selectedDramType] === min)?.date || '-';
    const current = chartData[chartData.length - 1]?.[selectedDramType] || 0;

    return { max, min, avg, current, maxDate, minDate };
  }, [chartData, selectedDramType]);

  // 📈 차트 데이터 재계산 (dramPeriod/selectedDramType 변화 감지)
  const processedChartData = useMemo(() => {
    if (dramData.length === 0) return [];

    // 1. 기간 필터링 (간단 예시: 6개월 이전은 제외 → 실제선은 날짜 파싱 필요)
    const filtered = dramData.slice(-6); // 예: 최근 6개월
    return filtered.map(d => ({
      date: d.date,
      [selectedDramType]: d[selectedDramType],
    }));
  }, [dramData, selectedDramType]);

  // 📊 데이터 변환 (Recharts에 맞춘 형식)
  useEffect(() => {
    // dramData 로드 시 초기화
    if (dramData.length > 0) {
      setChartData(processedChartData);
    }
  }, [dramData, processedChartData]);

  // 🧮 Admin 파서 로직 (개선: try/catch + trim + created_at)
  const handleUpdate = () => {
    try {
      const raw = adminText.trim();
      if (!raw) {
        setParseLog('⚠️ 입력값이 비어있습니다.');
        setAdminError('');
        return;
      }

      // 매우 단순한 파서 예시 (실제는 정규식/parse 조건 필요)
      // 예: "2024-01: 12.50, 2024-02: 13.20" → [{date:"2024-01", DDR5:12.50}, ...]
      const lines = raw.split('\n').filter(line => line.includes(':'));
      const parsed = lines.map(line => {
        const [dateStr, priceStr] = line.split(':').map(s => s.trim());
        const price = parseFloat(priceStr.replace(/,/g, ''));
        return {
          date: dateStr,
          DDR5: isNaN(price) ? 0 : price,
          // 여기서 추가 필드 자동 생성 (실제 구현 시 DDR4 등도 처리 가능)
        };
      });

      // created_at 필드 추가
      const now = new Date().toISOString();
      parsed.forEach(item => (item.created_at = now));

      // ✅ 성공 로그
      setDramData(parsed); // 실제 앱에선 setDramData(parsed) → state 업데이트
      setParseLog(`✅ ${parsed.length}개 행 파싱 성공 (예: DDR5: ${parsed[0]?.DDR5})`);
      setAdminError('');
    } catch (err) {
      console.error(err);
      setParseLog('❌ 파싱 중 오류 발생');
      setAdminError('❌ 데이터 형식을 확인해주세요. (예: YYYY-MM: 12.50)');
    }
  };

  // 🔁 Tab changed → chart data 재계산
  useEffect(() => {
    if (activeTab === 'dramexchange') {
      setChartData(processedChartData);
    }
  }, [activeTab, processedChartData]);

  // ✅ DRAMeXchange 데이터 (mock data 대신 실제 `dramData`를 사용한다고 가정)
  // dramData 없으면 빈 데이터 표시
  const displayData = activeTab === 'cafe' ? [] : chartData;

  return (
    <div className="min-h-screen bg-[#0e1117] text-[#e5e7eb] font-sans">
      {/* 상단 탭 네비게이션 */}
      <nav className="flex bg-[#1e1e1e] shadow-md sticky top-0 z-10">
        <button
          className={`flex-1 py-3 px-4 text-lg font-medium transition-colors ${
            activeTab === 'cafe' ? 'bg-[#262730] text-white border-b-2 border-[#3b82f6]' : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('cafe')}
        >
          🇰🇷 네이버 카페 (한국)
        </button>
        <button
          className={`flex-1 py-3 px-4 text-lg font-medium transition-colors ${
            activeTab === 'dramexchange' ? 'bg-[#262730] text-white border-b-2 border-[#3b82f6]' : 'text-gray-400 hover:text-white'
          }`}
          onClick={() => setActiveTab('dramexchange')}
        >
          🌍 DRAMeXchange (글로벌)
        </button>
      </nav>

      {/* 메인 콘텐츠 */}
      <main className="max-w-6xl mx-auto p-4 sm:p-6">
        {/* Stats Row: 공통으로 사용하므로 Tab에 관계없이 표시 */}
        {activeTab === 'dramexchange' && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-6">
            <StatCard label="최고가" value={calculatedStats.max} currency="$" decimals={2} />
            <StatCard label="최저가" value={calculatedStats.min} currency="$" decimals={2} />
            <StatCard label="평균" value={calculatedStats.avg} currency="$" decimals={2} />
            <StatCard label="현재" value={calculatedStats.current} currency="$" decimals={2} />
          </div>
        )}

        {/* Tab Content */}
        {activeTab === 'cafe' ? (
          <div className="space-y-6">
            {/* 네이버 카페 메인 UI (Mock) */}
            <div className="bg-[#1e1e1e] p-4 rounded-lg border border-[#333]">
              <h2 className="text-xl font-bold mb-4 text-blue-300">🔥 카페 실시간 인기 게시물</h2>
              <ul className="space-y-2 text-sm">
                {[1, 2, 3].map(i => (
                  <li key={i} className="flex items-center justify-between p-2 bg-[#262730] rounded hover:bg-[#333] cursor-pointer">
                    <span>DDR5 4800MHz 구매 추천</span>
                    <span className="text-green-400">+2</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          /* DRAMeXchange UI */
          <div className="space-y-6">
            {/* 기간/타입 필터 */}
            <div className="flex flex-col sm:flex-row gap-4 bg-[#1e1e1e] p-4 rounded-lg border border-[#333]">
              <div className="flex-1">
                <label className="text-xs text-gray-500 block mb-1">기간</label>
                <div className="flex gap-2">
                  {['1m', '3m', '6m', '1y'].map(p => (
                    <button
                      key={p}
                      onClick={() => setDramPeriod(p)}
                      className={`px-3 py-1 rounded text-sm transition ${
                        dramPeriod === p ? 'bg-blue-600 text-white' : 'bg-[#262730] hover:bg-[#333]'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-500 block mb-1">유형</label>
                <div className="flex gap-2">
                  {['DDR4', 'DDR5'].map(t => (
                    <button
                      key={t}
                      onClick={() => setSelectedDramType(t)}
                      className={`px-3 py-1 rounded text-sm transition ${
                        selectedDramType === t ? 'bg-blue-600 text-white' : 'bg-[#262730] hover:bg-[#333]'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 차트 */}
            <div className="h-64 sm:h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={displayData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" stroke="#9ca3af" />
                  <YAxis
                    domain={[0, 'dataMax']}
                    tickFormatter={(val) => `$${val.toFixed(2)}`}
                    stroke="#9ca3af"
                  />
                  <Tooltip
                    formatter={(value) => [`$${Number(value).toFixed(2)}`, selectedDramType]}
                    contentStyle={{ backgroundColor: '#1e1e1e', color: '#e5e7eb', border: '1px solid #333' }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey={selectedDramType}
                    stroke="#3b82f6"
                    activeDot={{ r: 6 }}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* 테이블 */}
            <div className="bg-[#1e1e1e] rounded-lg border border-[#333] overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm sm:text-base">
                  <thead className="bg-[#262730]">
                    <tr>
                      <th className="px-4 py-2 font-medium">날짜</th>
                      <th className="px-4 py-2 font-medium">가격 ($)</th>
                      <th className="px-4 py-2 font-medium">전일대비</th>
                      <th className="px-4 py-2 font-medium">세션</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#333]">
                    {displayData.length > 0 ? (
                      displayData.map((item, idx) => (
                        <tr
                          key={idx}
                          onClick={() => setSelectedDramProduct(item)}
                          className={`cursor-pointer hover:bg-[#262730] transition ${
                            selectedDramProduct?.date === item.date ? 'bg-blue-900/30' : ''
                          }`}
                        >
                          <td className="px-4 py-2 font-mono">{item.date}</td>
                          <td className="px-4 py-2 text-right font-medium">
                            ${Number(item[selectedDramType]).toFixed(2)}
                          </td>
                          <td className={`px-4 py-2 text-right font-bold ${
                            // ✅ 수정: +면 초록색, -면 빨간색 (일반 금융 규칙)
                            item.change?.includes('+') ? 'text-green-400' :
                            item.change?.includes('-') ? 'text-red-400' :
                            'text-gray-400'
                          }`}>
                            {item.change}
                          </td>
                          <td className="px-4 py-2">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                              item.session === '상승장' ? 'bg-green-900/30 text-green-300' :
                              item.session === '하락장' ? 'bg-red-900/30 text-red-300' :
                              'bg-gray-800 text-gray-300'
                            }`}>
                              {item.session || '-'}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                          데이터가 없습니다.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Admin Panel */}
        <div className="mt-8 bg-[#1e1e1e] p-4 sm:p-6 rounded-lg border border-[#333]">
          <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
            <span>🛠️ Admin</span>
          </h3>
          <div className="space-y-3">
            <textarea
              className="w-full bg-[#0e1117] border border-[#333] rounded p-3 text-sm sm:text-base text-gray-200 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              rows={4}
              placeholder={
                "예시:\n2024-01: 12.50\n2024-02: 13.20\n..."
              }
              value={adminText}
              onChange={(e) => setAdminText(e.target.value)}
              spellCheck={false}
            />
            <div className="flex items-center gap-3">
              <button
                onClick={handleUpdate}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition font-medium"
              >
                📥 업데이트
              </button>
              {adminError && (
                <span className="text-red-400 font-medium">{adminError}</span>
              )}
              <span className="text-gray-500 text-sm truncate flex-1 max-w-[200px]">
                {parseLog || '최근 로그 없음'}
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
