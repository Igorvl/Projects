import React, {useState, useEffect} from 'react';
import {
	followTh,
	unfollowTh,
	totalPages,
	selectedPage,
	choosedUserId,
	getUsersTh,
	currentUser,
} from "../../Redux/usersReducer";
import {connect} from "react-redux";
import UsersH from "./UsersH";
// import WithAuthRedirect from "../../HOC/withAuthRedirect";
import {Redirect} from "react-router-dom";

const UsersContainer = (props) => {
	
	let [preloaderOn, setPreloaderOn] = useState(false);
	let {usersOnPage, choosedPage, getUsersTh} = props;
	
// хук для запроса на серв. списка пользователей. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		getUsersTh(usersOnPage, choosedPage);
		setPreloaderOn(false);
	}, [usersOnPage, choosedPage, getUsersTh]);
	
	let paginationNums = [];
	for (let i = 1; i <= props.countPages; i++) {
		paginationNums.push(i);
	}
	
	// if (!props.isLoggedIn) return <Redirect to={'/login'} />;
	
	return <UsersH
		paginationNums={paginationNums}
		usersData={props.usersData}
		choosedPage={props.choosedPage}
		selectedPage={props.selectedPage}
		unfollowTh={props.unfollowTh}
		followTh={props.followTh}
		preloaderOn={preloaderOn}
		choosedUserId={props.choosedUserId}
		currentUser={props.currentUser}
	/>;
};

const mapStateToProps = (state) => {
	return ({
		usersData: state.usersPage.usersData,
		countPages: state.usersPage.countPages,
		currentPage: state.usersPage.currentPage,
		choosedPage: state.usersPage.choosedPage,
		usersOnPage: state.usersPage.usersOnPage,
		currentUser: state.usersPage.currentUser,
		isLoggedIn: state.auth.isLoggedIn,
	})
};

const WithAuthRedirect = (Component) => {
	class RedirectComponent extends React.Component  {
		render() {
			if (!this.props.isLoggedIn) return <Redirect to={'/login'}/>;
			return <Component {...this.props}/>
		}
	}
	return RedirectComponent
};


let AuthRedirectComponent = WithAuthRedirect(UsersContainer);

export default connect(mapStateToProps, {
	followTh, unfollowTh, totalPages, selectedPage, choosedUserId, getUsersTh, currentUser
})(AuthRedirectComponent);

