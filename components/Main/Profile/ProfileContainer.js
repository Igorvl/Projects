import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import {Redirect, withRouter} from 'react-router-dom';
import Profile from "./Profile";
import {choosedUserId, currentUser} from "../../Redux/usersReducer";
import {profileRequest} from "../../Redux/profileReducer";
import withAuthRedirect from "../../HOC/withAuthRedirect";
import {compose} from "redux";

const ProfileContainer = (props) => {
		
		let [preloaderOn, setPreloaderOn] = useState(false);
		let {UserId} = props;
// хук для запроса на серв. профиля пользователя.
		useEffect(() => {
				setPreloaderOn(true);
				profileRequest(UserId);
				setPreloaderOn(false);
			}, [UserId]
		);
	
	if (!props.isLoggedIn) return <Redirect to={'/login'} />;
		return <Profile
			choosedUser={props.choosedUser}
			preloaderOn={preloaderOn}
		/>
	};

const mapStateToProps = (state) => {
	return ({
		UserId: state.usersPage.choosedUserId,
		choosedUser: state.usersPage.currentUser,
	})
};

// все ф-и последовательной обработки ProfileContainer переносим в конвеер compose (ф-я Redux). Порядок выполнения:
// withRouter, withAuthRedirect, connect
export default compose(
	connect(mapStateToProps, {	choosedUserId, currentUser }),
	// получение id пользователя из параметра ссылки. withRouter - HOC возвращающий параметры строки в props.
	// В ссылке в App.js указать параметр ':userId?'
	withAuthRedirect,
	withRouter,
)(ProfileContainer);


