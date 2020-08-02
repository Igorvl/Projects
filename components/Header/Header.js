import React from 'react';
import logo from '../../Images/logo.svg';
import loupe from '../../Images/head_loupe.svg';
import camera from '../../Images/camera_50.png';
import s from '../../css/Header.module.css';
import {NavLink} from "react-router-dom";

export default (props) => {
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
						{props.isLoggedIn ?
							<div className={s.loginBlock} onClick={() => props.profileRequest(props.id)}>
								<NavLink to={'/profile/' + props.id}>
									<div className={s.loginBlock} >
										<span className={s.loginBlock__name}>{props.login}</span>
										<img src={camera} className={s.loginBlock__camera} alt=""/>
									</div>
								</NavLink>
							</div> :
							<NavLink to={'/login'}>
								<span>{'Login'}</span>
								<img src={camera} className={s.loginBlock__camera} alt=""/>
							</NavLink>
						}
					</div>
				</div>
			</header>
		</div>
	);
}


