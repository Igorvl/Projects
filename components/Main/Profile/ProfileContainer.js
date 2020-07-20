import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import {withRouter} from 'react-router-dom';
import Profile from "./Profile";
import {choosedUserId, currentUser} from "../../Redux/usersReducer";
import {profileRequest} from "../../Redux/profileReducer";

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


export default connect(mapStateToProps, {
	// callBacks for mapDispatchToProps
	choosedUserId, currentUser
})(ProfileContainerWithParam);

