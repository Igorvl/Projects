import React from 'react';
import s from '../../css/Navbar.module.css';
import logoNav from "../../Images/logo.svg"
import {NavLink} from "react-router-dom";

export default () => {
	return (
		<nav className={s.leftNav}>
			<ul className={s.nav_ul}>
				<li>
					<NavLink to="/profile" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Profile
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/dialogs" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Messages
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/users" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Users
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/news" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										News
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/music" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Music
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/games" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Games
									</span>
					</NavLink>
				</li>
				<li>
					<NavLink to="/settings" className={s.nav_link} activeClassName={s.navLinkActive}>
						<img src={logoNav} className={s.logo_nav} alt=""/>
						<span className={s.nav_txt}>
										Settings
									</span>
					</NavLink>
				</li>
			</ul>
		</nav>
	);
};

