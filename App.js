import React from 'react';
import s from './css/App.module.css';
import {Route} from "react-router-dom";
import Header from "./components/Header/Header";
import Navbar from "./components/Main/Navbar";
import MainAside from "./components/Main/MainAside";
import Music from "./components/Main/Music/Music";
import Games from "./components/Main/Games/Games";
import News from "./components/Main/News/News";
import Settings from "./components/Main/Settings/Settings";
import DialogsContainer from "./components/Main/Dialogs/DialogsContainer";
import UsersContainer from "./components/Main/Users/UsersContainer";
import ProfileContainer from "./components/Main/Profile/ProfileContainer";

export default (props) => {
	return (
			<div className={s.app}>
				<Header/>
				<main className={s.body}>
					<Navbar/>
					<div className={s.mainField}>
						<Route render={()=> <ProfileContainer/>} path={'/profile/:userId?'}/>
						<Route render={()=> <DialogsContainer/>} path={'/dialogs'}/>
						<Route render={()=> <UsersContainer/>} path={'/users'}/>
						<Route render={()=> <Music/>} path={'/music'}/>
						<Route render={()=> <Games/>} path={'/games'}/>
						<Route render={()=> <News/>} path={'/news'}/>
						<Route render={()=> <Settings/>} path={'/settings'}/>
					</div>
					<MainAside/>
				</main>
			</div>
	);
};

