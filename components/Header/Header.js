import React from 'react';
import logo from '../../Images/logo.svg';
import loupe from '../../Images/head_loupe.svg';
import camera from '../../Images/camera_50.png';
import s from '../../css/Header.module.css';

export default () => {
	return (
		<div className={s.app}>
			<header className={s.appHeader}>
				<div className={s.container}>
					<div className={s.logoCont}>
						<img src={logo} className={s.logo} alt="logo"/>
						<span className={s.logoCont_tag}>#лучшеНЕдома</span>
					</div>
					
					<div className={s.centerBlock}>
						<div className={s.centerBlock__search}>
							<img src={loupe} alt=""/>
							<span>Поиск</span>
						</div>
					</div>
					
					<div className={s.loginBlock}>
						{/* eslint-disable-next-line jsx-a11y/anchor-is-valid */}
						<a href="#">
							<span>Login</span>
							<img src={camera} className={s.loginBlock__camera} alt=""/>
						</a>
					</div>
				</div>
			</header>
		</div>
	);
}


