import React, {useState, useEffect} from 'react';
import {choosedUserId} from "../../Redux/usersReducer";
import {connect} from "react-redux";
import * as axios from "axios";
import Profile from "./Profile";

let user;
const ProfileContainer = (props) => {

let [preloaderOn, setPreloaderOn] = useState(false);
let [choosedUser, setChoosedUser] = useState({
	"aboutMe": null,
	"contacts": {
		"facebook": null,
		"website": null,
		"vk": null,
		"twitter": null,
		"instagram": null,
		"youtube": null,
		"github": null,
		"mainLink": null
	},
	"lookingForAJob": true,
	"lookingForAJobDescription": null,
	"fullName": null,
	"userId": null,
	"photos": {
		"small": null,
		"large": null
	}
});

// хук для запроса на серв. профиля пользователя.
useEffect(() => {
	setPreloaderOn(true);
	axios.get(`https://social-network.samuraijs.com/api/1.0/profile/${props.UserId}`).then(response => {
		setChoosedUser(prevState => {return {...prevState, ...response.data}});
		setPreloaderOn(false);
		user = choosedUser;
	})
}, []);


return <Profile
	userId = {props.UserId}
	choosedUser = {choosedUser}
	// choosedUserId = {props.choosedUserId}
/>

};

const mapStateToProps = (state) => {
	return ({
		UserId: state.usersPage.choosedUserId,
		choosedUser: state.choosedUser,
	})
};

export default connect(mapStateToProps, {
	// callBacks for mapDispatchToProps
	choosedUserId,})(ProfileContainer);

