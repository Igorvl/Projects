import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import {withRouter} from 'react-router-dom';
import * as axios from "axios";
import Profile from "./Profile";
import {choosedUserId, currentUser} from "../../Redux/usersReducer";

const ProfileContainer = (props) => {

let [preloaderOn, setPreloaderOn] = useState(false);

// хук для запроса на серв. профиля пользователя.
useEffect(() => {
	setPreloaderOn(true);
	axios.get(`https://social-network.samuraijs.com/api/1.0/profile/${props.match.params.userId ? props.match.params.userId : '2'}`).then(response => {
		props.currentUser(response.data);
		setPreloaderOn(false);
	})
}, [props.match.params.userId, props.UserId]);


return <Profile
	choosedUser = {props.choosedUser}
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


export default connect(mapStateToProps, {
	// callBacks for mapDispatchToProps
	choosedUserId, currentUser})(ProfileContainerWithParam);

