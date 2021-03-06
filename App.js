import React from 'react';
import s from './css/App.module.css';
import {Route} from "react-router-dom";
import Navbar from "./components/Main/Navbar";
import MainAside from "./components/Main/MainAside";
import Music from "./components/Main/Music/Music";
import Games from "./components/Main/Games/Games";
import News from "./components/Main/News/News";
import Settings from "./components/Main/Settings/Settings";
import DialogsContainer from "./components/Main/Dialogs/DialogsContainer";
import UsersContainer from "./components/Main/Users/UsersContainer";
import ProfileContainer from "./components/Main/Profile/ProfileContainer";
import HeaderContainer from "./components/Header/HeaderContainer";
import LoginContainer from "./components/Login/LoginContainer";

export default (props) => {
	return (
		<div className={s.app}>
			<HeaderContainer>
				<Route render={() => <HeaderContainer/>} path={'/profile/:userId'}/>
			</HeaderContainer>
			<main className={s.body}>
				<Navbar/>
				<div className={s.mainField}>
					<Route exact render={() => <ProfileContainer/>} path={'/profile/:userId?'}/>
					<Route render={() => <DialogsContainer/>} path={'/dialogs'}/>
					<Route render={() => <UsersContainer/>} path={'/users'}/>
					<Route render={() => <Music/>} path={'/music'}/>
					<Route render={() => <Games/>} path={'/games'}/>
					<Route render={() => <News/>} path={'/news'}/>
					<Route render={() => <Settings/>} path={'/settings'}/>
					<Route render={() => <LoginContainer/>} path={'/login'}/>
				</div>
				<MainAside/>
			</main>
		</div>
	);
};

