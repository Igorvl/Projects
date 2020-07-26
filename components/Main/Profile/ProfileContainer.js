import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import {Redirect, withRouter} from 'react-router-dom';
import Profile from "./Profile";
import {choosedUserId, currentUser} from "../../Redux/usersReducer";
import {profileRequest} from "../../Redux/profileReducer";
import withAuthRedirect from "../../HOC/withAuthRedirect";

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

// получение id пользователя из параметра ссылки. withRouter - HOC возвращающий параметры строки в props.
// В ссылке в App.js указать параметр ':userId?'
let ProfileContainerWithParam = withRouter(ProfileContainer);

let AuthRedirectComponent = withAuthRedirect(ProfileContainerWithParam);

export default connect(mapStateToProps, {	choosedUserId, currentUser })(AuthRedirectComponent);

