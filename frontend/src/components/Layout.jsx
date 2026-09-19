import { NavLink, Outlet } from 'react-router-dom';

import ToastProvider from './Toast.jsx';

const NAV_GROUPS = [
  {
    items: [
      { to: '/', label: '总览看板', icon: '📊', end: true },
      { to: '/restrooms', label: '公厕台账', icon: '🏛️' },
      { to: '/inspections', label: '保洁巡查', icon: '🧹' },
      { to: '/issues', label: '问题整改', icon: '🛠️' },
    ],
  },
  {
    title: '保洁服务外包',
    items: [
      { to: '/vendors', label: '外包单位', icon: '🏢' },
      { to: '/contracts', label: '外包合同', icon: '📄' },
      { to: '/settlements', label: '月度费用台账', icon: '💰' },
    ],
  },
];

export default function Layout() {
  return (
    <ToastProvider>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <strong>公厕保洁巡查记录系统</strong>
            <span>台账 · 巡查 · 问题 · 外包结算</span>
          </div>
          <nav>
            {NAV_GROUPS.map((group, groupIndex) => (
              <div className="nav-group" key={group.title || `group-${groupIndex}`}>
                {group.title ? <div className="nav-group-title">{group.title}</div> : null}
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                  >
                    <span className="nav-icon" aria-hidden="true">
                      {item.icon}
                    </span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div>接口文档：/docs</div>
            <div>版本 v1.1.0</div>
          </div>
        </aside>
        <div className="main">
          <Outlet />
        </div>
      </div>
    </ToastProvider>
  );
}
