import React from 'react';
import s from '../../css/MainAside.module.css';

export default () => {
	return (
		<aside className={s.mainAside}>
			<nav className={s.asideNav}>
				<ul className={s.nav_ul}>
					<li><a className={s.nav_link} href="http://localhost:3000">Новости</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Рекомендации</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Поиск</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Избранное</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Новое</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Замечания</a></li>
					<li><a className={s.nav_link} href="http://localhost:3000">Самое интересное</a></li>
				</ul>
			</nav>
		</aside>
	);
};

